#!/usr/bin/env python3
"""Install/update the Pi service and add its HTTPS site to Caddy."""
import argparse
import json
import os
from pathlib import Path
import pwd
import re
import shutil
import subprocess
import sys
import tempfile
import time
from urllib.request import urlopen

SOURCE = Path(__file__).resolve().parents[1]
CONFIG_DIR = Path("/etc/boat-maintenance")
INSTALL_DIR = Path("/opt/boat-maintenance-log")
CONFIG = CONFIG_DIR / "config.json"
SITE = Path("/etc/caddy/boat-maintenance.caddy")
CADDYFILE = Path("/etc/caddy/Caddyfile")
IMPORT = "import /etc/caddy/boat-maintenance.caddy"


def run(*args):
    subprocess.run(args, check=True)


def build_config(hostname, data_file, port=8765):
    if len(hostname) > 253 or not re.fullmatch(r"[a-zA-Z0-9](?:[a-zA-Z0-9.-]*[a-zA-Z0-9])?", hostname):
        raise ValueError("Use a hostname only, such as trickster-pi.local (no scheme, path, or port)")
    if any(not label or len(label) > 63 or label.startswith("-") or label.endswith("-") for label in hostname.split(".")):
        raise ValueError("Invalid hostname")
    data_file = Path(data_file).expanduser().resolve()
    if any(c in str(data_file) for c in ("\n", "\r", "%", '"', "\\")):
        raise ValueError("Data path contains unsupported characters")
    if not 1024 <= port <= 65535:
        raise ValueError("Backend port must be between 1024 and 65535")
    return {"data_file": str(data_file), "public_origin": "https://" + hostname.lower(), "backend_port": port}


def site_config(config):
    return f'''# Managed by Boat Maintenance Log. HTTPS is on standard port 443.
{config["public_origin"]} {{
    tls internal
    encode gzip
    reverse_proxy 127.0.0.1:{config["backend_port"]}
}}
'''


def service_config(user, config):
    parent = str(Path(config["data_file"]).parent)
    return f'''[Unit]
Description=Boat Maintenance Log API
After=network.target
RequiresMountsFor="{parent}"

[Service]
Type=simple
User={user}
WorkingDirectory={INSTALL_DIR}
ExecStart=/usr/bin/python3 {INSTALL_DIR}/server.py --config {CONFIG}
Restart=on-failure
RestartSec=5
UMask=0077
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hostname", help="Default: current Pi hostname plus .local")
    location = parser.add_mutually_exclusive_group()
    location.add_argument("--data-dir", type=Path, help="Folder for data.zip; may be inside your OneDrive folder")
    location.add_argument("--data-file", type=Path, help="Full path to the authoritative ZIP")
    initial = parser.add_mutually_exclusive_group()
    initial.add_argument("--init-from", type=Path, help="Use a newer exported ZIP on first setup instead of the bundled baseline")
    initial.add_argument("--new-boat", help="First setup with an empty dataset for this boat name")
    parser.add_argument("--user", help="Service account; defaults to the user who invoked sudo")
    parser.add_argument("--backend-port", type=int, help="Loopback-only API port; default 8765")
    args = parser.parse_args()
    if os.geteuid() != 0:
        parser.error("Run using sudo python3 scripts/install_pi.py")
    user = args.user or os.environ.get("SUDO_USER")
    if not user or user == "root":
        parser.error("Specify a non-root service user with --user")
    account = pwd.getpwnam(user)
    if not shutil.which("caddy") or not shutil.which("systemctl"):
        parser.error("First run: sudo apt update && sudo apt install -y python3 caddy")
    old = json.loads(CONFIG.read_text()) if CONFIG.exists() else {}
    hostname = args.hostname or old.get("public_origin", "").removeprefix("https://") or os.uname().nodename.split(".")[0] + ".local"
    data_file = args.data_file or (args.data_dir / "data.zip" if args.data_dir else None) or old.get("data_file") or Path(account.pw_dir) / ".local/share/boat-maintenance/data.zip"
    config = build_config(hostname, data_file, args.backend_port or old.get("backend_port", 8765))
    data_file = Path(config["data_file"])
    old_file = Path(old["data_file"]) if old else None
    moving = old_file is not None and old_file != data_file
    if (args.init_from or args.new_boat) and (data_file.exists() or old_file):
        parser.error("Server is already configured; first-setup options never replace existing data")
    if moving and data_file.exists():
        parser.error("Destination already contains data. Choose an empty destination or edit config.json deliberately")
    if old_file and not old_file.exists() and not args.init_from:
        parser.error("Configured data file is missing. Restore it or mount its drive; refusing to reset to baseline")
    source_data = args.init_from or (old_file if moving else SOURCE / "trickster-maintenance-data.zip")
    sys.path.insert(0, str(SOURCE))
    sys.dont_write_bytecode = True
    from server import decode_archive, initialize, empty_archive
    # Validate all selected data before touching services.
    initial_raw = empty_archive(args.new_boat, SOURCE / "trickster-maintenance-data.zip") if args.new_boat else None
    decode_archive(initial_raw if initial_raw is not None else (data_file if data_file.exists() else source_data).read_bytes())
    existing_caddy = CADDYFILE.read_text() if CADDYFILE.exists() else ""
    old_site = SITE.read_bytes() if SITE.exists() else None
    new_caddy = existing_caddy
    if IMPORT not in [line.strip() for line in existing_caddy.splitlines()]:
        new_caddy = existing_caddy.rstrip() + "\n\n" + IMPORT + "\n"
    SITE.parent.mkdir(parents=True, exist_ok=True)
    SITE.write_text(site_config(config))
    staged = CADDYFILE.with_name("boat-maintenance-validation.Caddyfile")
    try:
        staged.write_text(new_caddy)
        run("caddy", "validate", "--config", str(staged), "--adapter", "caddyfile")
    except Exception:
        if old_site is None:
            SITE.unlink(missing_ok=True)
        else:
            SITE.write_bytes(old_site)
        raise
    finally:
        staged.unlink(missing_ok=True)
    run("systemctl", "stop", "boat-maintenance.service") if subprocess.run(
        ["systemctl", "cat", "boat-maintenance.service"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0 else None
    try:
        # Stop the old HTTP service too; never leave port 8000 serving stale data.
        INSTALL_DIR.mkdir(parents=True, exist_ok=True)
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        if not data_file.parent.exists():
            run("runuser", "-u", user, "--", "mkdir", "-p", str(data_file.parent))
        if not data_file.exists():
            if initial_raw is not None:
                with tempfile.NamedTemporaryFile() as seed:
                    seed.write(initial_raw)
                    seed.flush()
                    initialize(data_file, seed.name)
            else:
                initialize(data_file, source_data)
            os.chown(data_file, account.pw_uid, account.pw_gid)
        # Atomic saves require permission on the containing folder, not just the file.
        run("runuser", "-u", user, "--", "test", "-w", str(data_file.parent))
        run("runuser", "-u", user, "--", "test", "-r", str(data_file))
        for name in ("server.py", "maintenance.html"):
            shutil.copyfile(SOURCE / name, INSTALL_DIR / name)
            os.chmod(INSTALL_DIR / name, 0o644)
        if CONFIG.exists():
            shutil.copyfile(CONFIG, CONFIG.with_suffix(".json.previous"))
        CONFIG.write_text(json.dumps(config, indent=2) + "\n")
        os.chmod(CONFIG, 0o644)
        service = Path("/etc/systemd/system/boat-maintenance.service")
        if service.exists():
            shutil.copyfile(service, CONFIG_DIR / "previous.service")
        service.write_text(service_config(user, config))
        if new_caddy != existing_caddy:
            if CADDYFILE.exists():
                shutil.copyfile(CADDYFILE, CADDYFILE.with_name("Caddyfile.before-boat-maintenance"))
            CADDYFILE.write_text(new_caddy)
        run("systemctl", "daemon-reload")
        run("systemctl", "enable", "boat-maintenance.service", "caddy.service")
        run("systemctl", "restart", "boat-maintenance.service")
        run("systemctl", "reload-or-restart", "caddy.service")
        for attempt in range(25):
            try:
                with urlopen(f'http://127.0.0.1:{config["backend_port"]}/api/health', timeout=2) as response:
                    if json.load(response).get("status") != "ok":
                        raise RuntimeError("Dataset health check failed")
                break
            except Exception:
                if attempt == 24:
                    raise RuntimeError("The server did not become ready; inspect the service log")
                time.sleep(0.2)
        run("systemctl", "is-active", "boat-maintenance.service", "caddy.service")
    except Exception:
        print("Installation did not finish. Inspect: sudo journalctl -u boat-maintenance -u caddy -n 60", file=sys.stderr)
        raise
    print("\nOpen " + config["public_origin"] + "/")
    print("Server data: " + str(data_file))
    print("Install Caddy's public root certificate on your other devices; see README.md.")
    if moving:
        print("Previous data was retained at " + str(old_file) + "; only the new location is live.")


if __name__ == "__main__":
    main()
