# SyncOver

Lightweight Linux monitor for local Syncthing sync errors, delivered through Pushover. Install on each device (Titan and Donnager). Python 3.9+; no third-party packages.

Checks folders every 60 seconds. Alerts after an unchanged error set persists for 120 seconds. Includes the device, folder and error details. Suppresses duplicate alerts across restarts and optionally sends recovery messages. API outages and offline devices are logged without notifications.

## Linux desktop installation (systemd)

On each machine, run as your normal user (without sudo):

```bash
git clone https://github.com/titandrive/SyncOver.git
cd SyncOver
python3 install.py
```

Already cloned it? Just run `python3 install.py` inside the SyncOver folder.

The installer asks for the device name, Syncthing address, and Pushover keys. It tries to find your local Syncthing API key automatically. Otherwise, copy it from Syncthing → Settings → GUI. Find your Pushover user key on your account dashboard and create an application for its application token. Both machines can share those Pushover credentials.

Setup sends a test notification, checks Syncthing, and starts the service automatically. Keys are entered privately and saved in `~/.config/syncover/config.json`, outside this repository. You can accept the default address for a standard local Syncthing installation. On servers, answer yes to running after logout; this step may ask for your sudo password.

### Update or change settings

```bash
git pull
python3 install.py
```

Press Enter to keep existing values. Additional settings (alert delay, polling interval, recovery notifications) are in `~/.config/syncover/config.json`; restart after editing.

### Status and stop

```bash
systemctl --user status syncover
journalctl --user -u syncover -f
systemctl --user disable --now syncover
```

### Uninstall

From the repository directory:

```bash
python3 install.py --uninstall
```

This stops and removes the service, installed application, saved API keys, settings, and default alert history. To keep settings and alert history for a future reinstall:

```bash
python3 install.py --uninstall --keep-config
```

The downloaded repository, custom state paths, and user lingering setting are preserved.

## Titan / Unraid (Docker Compose)

Enable Docker and have Docker Compose available on Unraid (for example through a Compose management plugin). This builds the image locally; no published image is required.

Keep the source on persistent storage:

```bash
cd /mnt/user/appdata
git clone https://github.com/titandrive/SyncOver.git syncover-source
cd syncover-source
mkdir -p /mnt/user/appdata/syncover
cp -n config.docker.example.json /mnt/user/appdata/syncover/config.json
chmod 600 /mnt/user/appdata/syncover/config.json
```

Edit `/mnt/user/appdata/syncover/config.json` and replace the three API key placeholders. The supplied Compose file uses host networking: `127.0.0.1:8384` works if Syncthing exposes its GUI/API on Titan's port 8384. If your Syncthing container uses a different published host port, change that port in `syncthing_url`. If Syncthing has its own LAN IP, use that IP instead. SyncOver does not need access to your synced files or Syncthing's appdata.

Test and launch from the source folder:

```bash
docker compose build
docker compose run --rm syncover --test-notification
docker compose run --rm syncover --once
docker compose up -d
```

Settings: `/mnt/user/appdata/syncover/config.json`. Alert state: `/mnt/user/appdata/syncover/state.json`. The application lives inside the container. Logs: `docker compose logs -f`. Configuration changes: `docker compose restart`. Updates: `git pull` followed by `docker compose up -d --build`.

The restart policy starts it again when Docker starts unless you explicitly stopped it. Ensure Unraid starts Docker automatically. Compose does not publish any SyncOver ports; the monitor has no web UI.

Uninstall: `docker compose down --rmi local`. This removes the container and locally built image, leaving settings and state in appdata. Delete `/mnt/user/appdata/syncover/config.json` and `/mnt/user/appdata/syncover/state.json` to remove those too. The source checkout remains separate.

## Behavior

Folders are tracked independently. Changed errors start a fresh grace period, so rapidly changing errors can postpone an alert. Paused folders are skipped. Failed API requests preserve incident state. Recovery requires an idle folder with no reported errors; it means errors cleared, not that every remote device is up to date. Removed folders retain their last incident state without a recovery message.

Delivery failures retry on later polls. A lost response or a crash after sending but before saving can cause duplicates. Run one copy per local Syncthing instance. Error details and file paths are sent to Pushover. HTTPS certificates are verified; local Syncthing defaults to loopback HTTP.

## Development

```bash
python3 -m unittest discover -s tests -v
```

References: [Syncthing errors](https://docs.syncthing.net/rest/folder-errors-get.html), [folder status](https://docs.syncthing.net/rest/db-status-get.html), [Pushover API](https://pushover.net/api).
