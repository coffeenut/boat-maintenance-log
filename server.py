#!/usr/bin/env python3
"""Boat Maintenance Log API. Run behind Caddy; never expose this listener."""
import argparse
import fcntl
import hashlib
import io
import json
import logging
import math
import os
from pathlib import Path, PurePosixPath
import secrets
import tempfile
import threading
import uuid
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit
from zipfile import ZipFile, ZIP_DEFLATED

APP_DIR = Path(__file__).resolve().parent
PATHS = {"manifest": "manifest.json", **{
    key: "data/" + key + (".jsonl" if key in ("service_history", "meter_readings") else ".json")
    for key in ("vessel", "equipment", "meters", "maintenance_tasks", "parts", "parties",
                "attachments", "service_history", "meter_readings")}}
MAX_BODY = 16 * 1024 * 1024
MAX_ARCHIVE = 128 * 1024 * 1024


class InvalidData(ValueError):
    pass


class Conflict(Exception):
    pass


def parse_json(raw):
    def invalid_constant(value):
        raise InvalidData("Non-finite JSON number: " + value)
    return json.loads(raw, parse_constant=invalid_constant)


def validate(files):
    """Check the shapes used by the UI before accepting a replacement snapshot."""
    def require(ok, message):
        if not ok:
            raise InvalidData(message)
    require(isinstance(files, dict) and set(files) == set(PATHS), "Incomplete dataset")
    manifest = files["manifest"]
    require(isinstance(manifest, dict), "Invalid manifest")
    require(manifest.get("format") == "boat-maintenance-data", "Unknown dataset format")
    require(isinstance(manifest.get("dataset_id"), str) and bool(manifest["dataset_id"]), "Missing dataset identity")
    require(manifest.get("schema_version") == "1.2.0", "Unsupported schema version")
    require(manifest.get("files") == {k: v for k, v in PATHS.items() if k != "manifest"}, "Unsupported dataset paths")
    for key in ("vessel", "equipment", "meters", "maintenance_tasks", "parts", "parties", "attachments"):
        doc = files[key]
        require(isinstance(doc, dict) and doc.get("file_type") == key, "Invalid " + key)
        require(doc.get("schema_version") == "1.2.0", "Unsupported " + key + " schema")
        records = [doc.get("record")] if key == "vessel" else doc.get("records")
        require(isinstance(records, list), "Missing records: " + key)
        ids = set()
        for record in records:
            require(isinstance(record, dict), "Invalid record: " + key)
            record_id = record.get("id")
            require(isinstance(record_id, str) and bool(record_id) and record_id not in ids,
                    "Missing or duplicate record ID: " + key)
            ids.add(record_id)
        if key in ("vessel", "equipment", "meters"):
            require(all(isinstance(r.get("name"), str) and bool(r["name"].strip()) for r in records), "Missing name: " + key)
    require(files["vessel"]["record"]["id"] == manifest.get("vessel_id"), "Vessel identity mismatch")
    for task in files["maintenance_tasks"]["records"]:
        require(isinstance(task.get("title"), str) and bool(task["title"].strip()), "Missing maintenance title")
        require(isinstance(task.get("active"), bool), "Invalid task status")
        require(task.get("task_kind") in ("recurring", "one_time"), "Invalid task kind")
        require(isinstance(task.get("schedule"), dict), "Missing schedule")
        triggers = task["schedule"].get("triggers")
        require(isinstance(triggers, list) and bool(triggers), "Empty schedule")
        for trigger in triggers:
            require(isinstance(trigger, dict) and trigger.get("type") in ("calendar", "meter", "date", "meter_value"), "Invalid schedule trigger")
            if trigger["type"] in ("calendar", "meter"):
                value = trigger.get("interval")
                require(type(value) in (int, float) and math.isfinite(value) and value > 0, "Invalid maintenance interval")
    for key in ("service_history", "meter_readings"):
        records = files[key]
        require(isinstance(records, list), "Invalid history: " + key)
        ids = set()
        for record in records:
            require(isinstance(record, dict), "Invalid history record")
            record_id = record.get("id")
            require(isinstance(record_id, str) and bool(record_id) and record_id not in ids, "Missing or duplicate history ID")
            ids.add(record_id)
            if key == "service_history":
                require(isinstance(record.get("date"), str) and isinstance(record.get("summary"), str), "Invalid service event")
                require(not ({"cost", "labor_hours"} & record.keys()), "Accounting fields are not supported")
            else:
                value = record.get("value")
                require(type(value) in (int, float) and math.isfinite(value) and value >= 0, "Invalid meter reading")
                require(isinstance(record.get("observed_at"), str), "Missing meter reading date")
    # Reject NaN/Infinity anywhere, including optional numeric fields.
    json.dumps(files, allow_nan=False)


def decode_archive(raw):
    if len(raw) > MAX_ARCHIVE:
        raise InvalidData("Data archive is too large")
    with ZipFile(io.BytesIO(raw)) as archive:
        entries = archive.infolist()
        if len(entries) > 10000 or sum(e.file_size for e in entries) > MAX_ARCHIVE:
            raise InvalidData("Expanded data archive is too large")
        names = [e.filename for e in entries if not e.is_dir()]
        if len(set(names)) != len(names):
            raise InvalidData("Duplicate archive paths")
        for name in names:
            if PurePosixPath(name).is_absolute() or ".." in PurePosixPath(name).parts or "\\" in name:
                raise InvalidData("Invalid archive path")
        prefix = ""
        if "manifest.json" not in names:
            manifests = [n for n in names if n.endswith("/manifest.json")]
            if len(manifests) != 1:
                raise InvalidData("Cannot find dataset manifest")
            prefix = manifests[0][:-len("manifest.json")]
        contents = {n[len(prefix):]: archive.read(n) for n in names if n.startswith(prefix)}
    files = {}
    for key, path in PATHS.items():
        if path not in contents:
            raise InvalidData("Missing " + path)
        text = contents[path].decode("utf-8")
        files[key] = [parse_json(line) for line in text.splitlines() if line.strip()] if path.endswith(".jsonl") else parse_json(text)
    validate(files)
    return files, contents


def encode_archive(files, contents):
    contents = dict(contents)
    for key, path in PATHS.items():
        if path.endswith(".jsonl"):
            text = "".join(json.dumps(r, ensure_ascii=False, allow_nan=False) + "\n" for r in files[key])
        else:
            text = json.dumps(files[key], ensure_ascii=False, indent=2, allow_nan=False) + "\n"
        contents[path] = text.encode("utf-8")
    output = io.BytesIO()
    with ZipFile(output, "w", ZIP_DEFLATED) as archive:
        for path, data in sorted(contents.items()):
            archive.writestr(path, data)
    raw = output.getvalue()
    if len(raw) > MAX_ARCHIVE:
        raise InvalidData("Data archive is too large")
    return raw


def atomic_write(path, raw):
    """Same-filesystem replace; never leave a partially written live dataset."""
    fd, temporary = tempfile.mkstemp(prefix=".boat-maintenance-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


class Store:
    def __init__(self, path):
        self.path = Path(path).resolve()
        self.lock = threading.Lock()
        self.snapshot()  # Missing/corrupt data is a startup error, never silently reset.

    def _read(self):
        if self.path.stat().st_size > MAX_ARCHIVE:
            raise InvalidData("Data archive is too large")
        raw = self.path.read_bytes()
        files, contents = decode_archive(raw)
        return raw, files, contents, hashlib.sha256(raw).hexdigest()

    def snapshot(self):
        with self.lock:
            _, files, _, revision = self._read()
            return {"files": files, "revision": revision}

    def save(self, files, revision):
        validate(files)
        with self.lock:
            raw, current, contents, current_revision = self._read()
            if files == current:
                # Safe retry after a successful write whose response was lost.
                return current_revision
            if revision != current_revision:
                raise Conflict("Another device saved changes. Reload the latest data before editing again.")
            if files["manifest"]["dataset_id"] != current["manifest"]["dataset_id"] or files["manifest"]["vessel_id"] != current["manifest"]["vessel_id"]:
                raise InvalidData("Dataset identity cannot be changed")
            new_raw = encode_archive(files, contents)
            atomic_write(self.path.with_name(self.path.name + ".bak"), raw)
            atomic_write(self.path, new_raw)
            return hashlib.sha256(new_raw).hexdigest()


class Server(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address, store, public_origin):
        self.store = store
        self.public_origin = public_origin
        self.csrf_token = secrets.token_urlsafe(32)
        super().__init__(address, Handler)


class Handler(BaseHTTPRequestHandler):
    def setup(self):
        super().setup()
        self.connection.settimeout(30)

    def reply(self, status, body=b"", content_type="application/json; charset=utf-8", etag=None):
        if not isinstance(body, bytes):
            body = json.dumps(body, ensure_ascii=False, allow_nan=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "same-origin")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'")
        if etag:
            self.send_header("ETag", '"' + etag + '"')
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def do_GET(self):
        path = urlsplit(self.path).path
        if path in ("/", "/maintenance.html"):
            self.reply(200, (APP_DIR / "maintenance.html").read_bytes(), "text/html; charset=utf-8")
        elif path == "/api/data":
            try:
                snapshot = self.server.store.snapshot()
                snapshot["csrf_token"] = self.server.csrf_token
                self.reply(200, snapshot, etag=snapshot["revision"])
            except Exception:
                logging.exception("Reading dataset failed")
                self.reply(503, {"error": "Server data is unavailable. Check the service log; no data was reset."})
        elif path == "/api/health":
            try:
                self.server.store.snapshot()
                self.reply(200, {"status": "ok"})
            except Exception:
                self.reply(503, {"status": "data unavailable"})
        else:
            self.reply(404, {"error": "Not found"})

    do_HEAD = do_GET

    def do_PUT(self):
        if urlsplit(self.path).path != "/api/data":
            self.reply(404, {"error": "Not found"})
            return
        if self.headers.get("Origin") != self.server.public_origin or not secrets.compare_digest(
                self.headers.get("X-CSRF-Token", ""), self.server.csrf_token):
            self.reply(403, {"error": "Connection expired or invalid origin. Reload the app before saving."})
            return
        if self.headers.get_content_type() != "application/json":
            self.reply(415, {"error": "Expected JSON"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = 0
        if not 0 < length <= MAX_BODY:
            self.reply(413, {"error": "Invalid or oversized request"})
            return
        try:
            payload = parse_json(self.rfile.read(length))
            if not isinstance(payload, dict) or not isinstance(payload.get("revision"), str):
                raise InvalidData("Missing data revision")
            revision = self.server.store.save(payload.get("files"), payload["revision"])
            self.reply(200, {"revision": revision}, etag=revision)
        except Conflict as error:
            self.reply(409, {"error": str(error)})
        except (ValueError, TypeError, KeyError, UnicodeError) as error:
            self.reply(422, {"error": "Invalid data: " + str(error)})
        except Exception:
            logging.exception("Saving dataset failed")
            self.reply(503, {"error": "The server could not confirm the save. Keep this page open and retry."})


def initialize(path, source):
    path = Path(path).resolve()
    if path.exists():
        raise FileExistsError("Refusing to overwrite existing server data: " + str(path))
    raw = Path(source).read_bytes()
    decode_archive(raw)
    path.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive creation also protects against two simultaneous initializations.
    with path.open("xb") as stream:
        os.chmod(path, 0o600)
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())


def empty_archive(name, baseline):
    """Reuse the portable format, with no vessel-specific records or source notes."""
    name = name.strip()
    if not name:
        raise InvalidData("Boat name is required")
    files, contents = decode_archive(Path(baseline).read_bytes())
    vessel_id = "ves_" + str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    files["manifest"].update(dataset_id="ds_" + str(uuid.uuid4()), vessel_id=vessel_id,
                             created_at=now, modified_at=now)
    files["vessel"]["record"] = {"id": vessel_id, "name": name, "vessel_type": "",
                                   "builder": "", "model": "", "year": None,
                                   "identifiers": [], "notes": ""}
    for key in ("equipment", "meters", "maintenance_tasks", "parts", "parties", "attachments"):
        files[key]["records"] = []
    files["service_history"] = []
    files["meter_readings"] = []
    validate(files)
    return encode_archive(files, {p: raw for p, raw in contents.items() if p.startswith("schemas/")})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--init-from", type=Path, help="Initialize missing data from a ZIP, then exit")
    args = parser.parse_args()
    config = parse_json(args.config.read_text())
    path = Path(config["data_file"]).expanduser()
    if not path.is_absolute():
        parser.error("data_file must be an absolute path")
    if args.init_from:
        initialize(path, args.init_from)
        print("Initialized " + str(path))
        return
    origin = config["public_origin"]
    parsed = urlsplit(origin)
    if parsed.scheme != "https" or not parsed.hostname or parsed.path or parsed.query or parsed.fragment or parsed.username:
        parser.error("public_origin must be an HTTPS origin such as https://trickster-pi.local")
    port = int(config.get("backend_port", 8765))
    if not 1024 <= port <= 65535:
        parser.error("backend_port must be between 1024 and 65535")
    # Only one server process may own this dataset. Never sync this lock file.
    with path.with_name(path.name + ".lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        server = Server(("127.0.0.1", port), Store(path), origin)
        logging.info("Serving %s via Caddy; loopback port %d", origin, port)
        try:
            server.serve_forever()
        finally:
            server.server_close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
