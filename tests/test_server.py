import copy
import io
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from zipfile import ZipFile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import server
from scripts.install_pi import build_config, service_config, site_config

SEED = server.APP_DIR / "trickster-maintenance-data.zip"


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "OneDrive folder" / "data.zip"
        server.initialize(self.path, SEED)
        self.store = server.Store(self.path)

    def edit(self, name="Updated boat"):
        snapshot = self.store.snapshot()
        snapshot["files"]["vessel"]["record"]["name"] = name
        return snapshot

    def test_save_survives_restart_and_retains_backup_and_other_files(self):
        original = self.path.read_bytes()
        snapshot = self.edit()
        revision = self.store.save(**snapshot)
        reopened = server.Store(self.path).snapshot()
        self.assertEqual(reopened["files"]["vessel"]["record"]["name"], "Updated boat")
        self.assertEqual(reopened["revision"], revision)
        self.assertEqual(self.path.with_name("data.zip.bak").read_bytes(), original)
        with ZipFile(io.BytesIO(original)) as before, ZipFile(self.path) as after:
            for name in before.namelist():
                if name not in server.PATHS.values():
                    self.assertEqual(before.read(name), after.read(name))

    def test_binary_attachment_is_preserved(self):
        files, contents = server.decode_archive(self.path.read_bytes())
        contents["attachments/photo.bin"] = bytes(range(256)) * 8
        self.path.write_bytes(server.encode_archive(files, contents))
        self.store.save(**self.edit())
        with ZipFile(self.path) as archive:
            self.assertEqual(archive.read("attachments/photo.bin"), contents["attachments/photo.bin"])

    def test_simultaneous_writers_only_one_wins(self):
        first, second = self.edit("First"), self.edit("Second")
        def save(snapshot):
            try:
                self.store.save(**snapshot)
                return "saved"
            except server.Conflict:
                return "conflict"
        with ThreadPoolExecutor(2) as pool:
            results = list(pool.map(save, [first, second]))
        self.assertCountEqual(results, ["saved", "conflict"])

    def test_lost_response_retry_is_idempotent(self):
        edit = self.edit()
        revision = self.store.save(**edit)
        backup = self.path.with_name("data.zip.bak").read_bytes()
        self.assertEqual(self.store.save(**edit), revision)
        self.assertEqual(self.path.with_name("data.zip.bak").read_bytes(), backup)

    def test_failed_atomic_replace_retains_live_dataset(self):
        original = self.path.read_bytes()
        real_replace = server.os.replace
        def fail_live(source, destination):
            if Path(destination) == self.path:
                raise OSError("simulated disk failure")
            return real_replace(source, destination)
        with patch("server.os.replace", side_effect=fail_live):
            with self.assertRaises(OSError):
                self.store.save(**self.edit())
        self.assertEqual(self.path.read_bytes(), original)
        self.assertFalse(list(self.path.parent.glob(".boat-maintenance-*")))

    def test_validation_rejects_incomplete_and_invalid_data_without_writing(self):
        original = self.path.read_bytes()
        mutations = [
            lambda f: f.pop("equipment"),
            lambda f: f["manifest"].update(dataset_id="different"),
            lambda f: f["meter_readings"][0].update(value=-1),
            lambda f: f["service_history"][0].update(labor_hours=2),
            lambda f: f["equipment"]["records"].append(copy.deepcopy(f["equipment"]["records"][0])),
        ]
        for mutate in mutations:
            with self.subTest(mutate=mutate):
                edit = self.edit()
                mutate(edit["files"])
                with self.assertRaises(server.InvalidData):
                    self.store.save(**edit)
                self.assertEqual(self.path.read_bytes(), original)

    def test_initialization_never_overwrites(self):
        before = self.path.read_bytes()
        with self.assertRaises(FileExistsError):
            server.initialize(self.path, SEED)
        self.assertEqual(self.path.read_bytes(), before)

    def test_missing_or_corrupt_file_never_resets(self):
        self.path.unlink()
        with self.assertRaises(FileNotFoundError):
            server.Store(self.path)
        self.assertFalse(self.path.exists())
        self.path.write_bytes(b"damaged")
        with self.assertRaises(Exception):
            server.Store(self.path)
        self.assertEqual(self.path.read_bytes(), b"damaged")

    def test_external_change_rejects_stale_snapshot(self):
        edit = self.edit("Local")
        files, contents = server.decode_archive(self.path.read_bytes())
        files["vessel"]["record"]["name"] = "Restored"
        self.path.write_bytes(server.encode_archive(files, contents))
        with self.assertRaises(server.Conflict):
            self.store.save(**edit)

    def test_new_boat_has_no_trickster_records_or_source_notes(self):
        raw = server.empty_archive("Sea Otter", SEED)
        files, contents = server.decode_archive(raw)
        self.assertEqual(files["vessel"]["record"]["name"], "Sea Otter")
        self.assertEqual(files["service_history"], [])
        self.assertEqual(files["meter_readings"], [])
        for key in ("equipment", "meters", "maintenance_tasks", "parts", "parties", "attachments"):
            self.assertEqual(files[key]["records"], [])
        self.assertNotIn("OWNER_MAINTENANCE_LOG.md", contents)
        self.assertNotIn("Trickster", json.dumps(files))
        self.assertNotEqual(files["manifest"]["dataset_id"], self.store.snapshot()["files"]["manifest"]["dataset_id"])


class APITests(unittest.TestCase):
    def setUp(self):
        StoreTests.setUp(self)
        self.http = server.Server(("127.0.0.1", 0), self.store, "https://boat.local")
        thread = threading.Thread(target=self.http.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(self.http.server_close)
        self.addCleanup(self.http.shutdown)
        self.base = "http://127.0.0.1:" + str(self.http.server_port)

    def request(self, path, data=None, headers=None, method=None):
        request = Request(self.base + path, data=json.dumps(data).encode() if data is not None else None,
                          headers=headers or {}, method=method or ("PUT" if data is not None else "GET"))
        try:
            response = urlopen(request, timeout=5)
        except HTTPError as error:
            response = error
        with response:
            return response.status, response.read(), response.headers

    def test_api_save_and_conflict(self):
        status, body, headers = self.request("/api/data")
        snapshot = json.loads(body)
        self.assertEqual(status, 200)
        self.assertEqual(headers["Cache-Control"], "no-store")
        write_headers = {"Content-Type": "application/json", "Origin": "https://boat.local", "X-CSRF-Token": snapshot.pop("csrf_token")}
        stale = copy.deepcopy(snapshot)
        snapshot["files"]["vessel"]["record"]["name"] = "From the browser"
        self.assertEqual(self.request("/api/data", snapshot, write_headers)[0], 200)
        stale["files"]["vessel"]["record"]["name"] = "Stale edit"
        self.assertEqual(self.request("/api/data", stale, write_headers)[0], 409)

    def test_csrf_and_content_type_rejections(self):
        snapshot = json.loads(self.request("/api/data")[1])
        headers = {"Content-Type": "application/json", "Origin": "https://boat.local", "X-CSRF-Token": snapshot.pop("csrf_token")}
        self.assertEqual(self.request("/api/data", snapshot, {**headers, "Origin": "https://other.example"})[0], 403)
        self.assertEqual(self.request("/api/data", snapshot, {**headers, "X-CSRF-Token": "wrong"})[0], 403)
        self.assertEqual(self.request("/api/data", snapshot, {**headers, "Content-Type": "text/plain"})[0], 415)

    def test_filesystem_is_not_exposed(self):
        for path in ("/.git/config", "/server.py", "/data.zip", "/trickster-maintenance-data.zip", "/dataset/data/vessel.json", "/../config.json"):
            self.assertEqual(self.request(path)[0], 404, path)
        self.assertEqual(self.request("/")[0], 200)
        self.assertEqual(self.request("/api/health")[0], 200)


class InstallerTests(unittest.TestCase):
    def test_quoted_data_path_and_standard_https(self):
        config = build_config("Boat-Pi.local", "/home/john/OneDrive/Boat Data/data.zip")
        self.assertEqual(config["public_origin"], "https://boat-pi.local")
        self.assertIn('RequiresMountsFor="/home/john/OneDrive/Boat Data"', service_config("john", config))
        self.assertIn("tls internal", site_config(config))
        self.assertIn("reverse_proxy 127.0.0.1:8765", site_config(config))

    def test_invalid_hostname_and_injected_path_rejected(self):
        for host in ("https://boat.local", "boat.local:443", "boat.local {", "a..local", "boat.local\n"):
            with self.assertRaises(ValueError):
                build_config(host, "/tmp/data.zip")
        with self.assertRaises(ValueError):
            build_config("boat.local", "/tmp/data\nInjected.zip")


if __name__ == "__main__":
    unittest.main()
