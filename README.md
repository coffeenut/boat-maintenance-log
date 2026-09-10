# Boat Maintenance Log

**v0.22: server-only, shared maintenance records for M/V Trickster.**

Open `https://YOUR-PI-HOSTNAME.local/`. All devices use the same server data. Submitting a work entry, meter reading, or equipment/schedule change automatically saves it on the Pi. The header confirms when the server has saved it.

There is no browser database, offline mode, or data-file upload/download interface. Unsubmitted entries and changes awaiting a successful save exist only in the open page. Keep it open if a save fails. The work-history CSV report remains available; it is not a data backup.

Use **Setup → Boat Settings** to change the boat name, type, builder, model, year, hull number, and notes. These details are saved on the server and shared across devices.

## Install on Raspberry Pi OS

Requires Raspberry Pi OS/Debian with systemd and Python 3.9 or newer. Run from the cloned repository as your normal Pi user:

```bash
git pull --ff-only
sudo apt update
sudo apt install -y python3 caddy avahi-daemon
sudo python3 scripts/install_pi.py
```

The installer prints your HTTPS address. First-install defaults:

- Address: `https://<Pi-hostname>.local/`, standard HTTPS port **443**.
- HTTP on port **80** redirects to HTTPS for that hostname.
- Data: `~/.local/share/boat-maintenance/data.zip`, belonging to your normal Pi user.
- Caddy handles HTTPS; the Python API listens only on `127.0.0.1:8765`. That internal port is not used in the browser or accessible from other computers.
- Both services start on boot. The installer replaces the earlier `boat-maintenance` service, stopping its port-8000 server.

If your package sources do not contain Caddy, use its [official Debian/Raspbian instructions](https://caddyserver.com/docs/install#debian-ubuntu-raspbian), then rerun the installer.

### Choose the data folder, including OneDrive

Use this instead of the last installation command:

```bash
sudo python3 scripts/install_pi.py \
  --hostname "$(hostname -s).local" \
  --data-dir "$HOME/OneDrive/Trickster/Maintenance"
```

Or specify a full filename using `--data-file "/absolute/path/maintenance.zip"`. Do not use both location flags. Quote paths containing spaces.

Use a **local, writable filesystem folder**. A OneDrive sync client must be set up separately; choosing a folder does not activate cloud backup. Back up `data.zip` and `data.zip.bak`; exclude `*.lock` and `.boat-maintenance-*` temporary files.

Use OneDrive as backup from this Pi, not as a way for multiple servers to edit live data. Prefer one-way backup and cloud version history: two-way sync can replace live data with a cloud version. Stop the service before restoring or editing a cloud copy. A mounted cloud drive is not supported as the live directory; saves require local filesystem atomic-replace semantics.

To move an existing installation, rerun the installer with `--data-dir`. It stops the app, copies current data into the new folder, and restarts. The original is retained; only the new location is live. It refuses to overwrite an existing destination. Running without flags preserves existing settings.

### Preserve newer v0.21 records

The bundled ZIP is the August 29, 2026 Trickster baseline. If you added newer records in the old browser app, export its Data ZIP once **before upgrading**, copy it onto the Pi, and initialize with it:

```bash
sudo python3 scripts/install_pi.py \
  --data-dir "$HOME/OneDrive/Trickster/Maintenance" \
  --init-from "$HOME/Downloads/my-latest-maintenance-data.zip"
```

`--init-from` is an administrator's first-install migration option. It refuses to overwrite existing server data. No upload option exists in the new app. Old browser caches are not imported automatically. Missing/corrupt server data is never silently replaced with baseline data.

## First setup for a different boat

Start with an empty equipment list, maintenance schedule, and work history:

```bash
sudo python3 scripts/install_pi.py \
  --new-boat "Your Boat Name" \
  --data-dir "$HOME/OneDrive/BoatMaintenance"
```

Then fill in **Boat Settings**, add equipment and meters, and create maintenance schedules. This option does not include Trickster's records and never replaces an existing installation's data. Without `--new-boat` or `--init-from`, first setup uses the verified Trickster baseline. Changing the name in Boat Settings updates the boat's details; it does not clear equipment or history.

## Trust HTTPS on each device (once)

Caddy creates and renews local certificates. Your other devices must trust its local root certificate to use `.local` HTTPS without certificate errors. Installing trust on the Pi does not install it on your laptop or phone. [Caddy local HTTPS documentation](https://caddyserver.com/docs/automatic-https#local-https).

After installation, copy the **public root certificate** into your Pi user's home:

```bash
sudo install -m 0644 \
  /var/lib/caddy/.local/share/caddy/pki/authorities/local/root.crt \
  "$HOME/boat-maintenance-root.crt"
```

On your Windows laptop, run in PowerShell, replacing the SSH user and hostname:

```powershell
scp YOUR_PI_USER@YOUR_PI_HOST:~/boat-maintenance-root.crt .
Import-Certificate -FilePath .\boat-maintenance-root.crt -CertStoreLocation Cert:\CurrentUser\Root
```

Restart the browser and open the exact hostname printed by the installer. On macOS/iPhone/iPad, install the public root certificate and enable trust in the device's certificate settings. Firefox may require importing it under certificate authorities if it does not use OS trust. Never distribute Caddy's private CA keys.

If the hostname does not resolve, check that devices share the same LAN and `avahi-daemon` is running on the Pi. Certificate trust does not configure name resolution. Local HTTPS works without internet access after setup.

This setup is for your private home/boat network. There is no app login: anyone who can reach the HTTPS address can read and edit records. Do not port-forward it to the internet.

## Updates and configuration

From the Git checkout:

```bash
git pull --ff-only
sudo python3 scripts/install_pi.py
```

The installer copies the app into `/opt/boat-maintenance-log`; live data stays outside the checkout. Updates preserve settings and existing data. Refresh older browser tabs after updates.

Settings live in `/etc/boat-maintenance/config.json`:

```json
{
  "data_file": "/home/john/OneDrive/Trickster/Maintenance/data.zip",
  "public_origin": "https://trickster-pi.local",
  "backend_port": 8765
}
```

Use installer flags to change hostname or backend port, keeping Caddy and the API consistent. If manually editing the data path, stop the service, put the data at the new location, set ownership for the service user, and restart.

Caddy configuration is `/etc/caddy/boat-maintenance.caddy`, imported by `/etc/caddy/Caddyfile`. The installer preserves other sites and validates the combined configuration. Ports 80/443 must be available to Caddy; an existing different web server needs to be integrated or reconfigured first.

```bash
sudo systemctl status boat-maintenance caddy --no-pager
sudo journalctl -u boat-maintenance -u caddy -n 60 --no-pager
sudo systemctl restart boat-maintenance
```

## Saving and recovery

- The authoritative ZIP contains readable JSON/JSONL, schemas, source notes, and existing attachments.
- Each save flushes a temporary ZIP and atomically replaces the live file. `data.zip.bak` retains the previous committed version, not a complete backup history.
- Revision checks reject stale edits with HTTP 409. Refresh asks before discarding unsaved work; one device cannot silently overwrite another's save.
- Pages check for updates every 15 seconds and on focus. Background refresh does not replace entered form text.
- If disconnected, edits remain only in that page's memory. Retry and wait for confirmation. There is no offline storage.
- Only one server process may own a data file. Cloud restores do not participate in that lock.

To restore, stop `boat-maintenance`, retain a copy of the current file, place a known-good ZIP at the configured path, ensure the service user can read it and write its directory, then restart. Refresh all browser tabs. Missing/corrupt data produces an error, not a new dataset.

## Development

`server.py` uses Python's standard library behind Caddy. Only `/`, `/maintenance.html`, `/api/data`, and `/api/health` are served. The Git checkout, data ZIP, backups, and configuration are not static downloads.

`GET /api/data` returns the dataset, revision, and same-origin write token. `PUT /api/data` validates a complete snapshot and revision before saving. Writes require the configured HTTPS Origin and token. These checks protect against cross-site writes, not against LAN users who can open the app.

```bash
python3 -m unittest discover -s tests -v
```

`dataset/` and `trickster-maintenance-data.zip` remain seed/reference data. Live edits never modify the repository. Keep the interface understandable to nontechnical boaters and do not add labor or service-cost accounting fields.
