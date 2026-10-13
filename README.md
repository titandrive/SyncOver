# SyncOver

Lightweight Linux monitor for local Syncthing sync errors, delivered through Pushover. Install on each device (Titan and Donnager). Python 3.9+; no third-party packages.

Checks folders every 60 seconds. Alerts after an unchanged error set persists for 120 seconds. Includes the device, folder and error details. Suppresses duplicate alerts across restarts and optionally sends recovery messages. API outages and offline devices are logged without notifications.

## Install

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

## Behavior

Folders are tracked independently. Changed errors start a fresh grace period, so rapidly changing errors can postpone an alert. Paused folders are skipped. Failed API requests preserve incident state. Recovery requires an idle folder with no reported errors; it means errors cleared, not that every remote device is up to date. Removed folders retain their last incident state without a recovery message.

Delivery failures retry on later polls. A lost response or a crash after sending but before saving can cause duplicates. Run one copy per local Syncthing instance. Error details and file paths are sent to Pushover. HTTPS certificates are verified; local Syncthing defaults to loopback HTTP.

## Development

```bash
python3 -m unittest discover -s tests -v
```

References: [Syncthing errors](https://docs.syncthing.net/rest/folder-errors-get.html), [folder status](https://docs.syncthing.net/rest/db-status-get.html), [Pushover API](https://pushover.net/api).
