# SyncOver

Lightweight Linux monitor for local Syncthing sync errors, delivered through Pushover. Install on each device (Titan and Donnager). Python 3.9+; no third-party packages.

Checks folders every 60 seconds. Alerts after an unchanged error set persists for 120 seconds. Includes the device, folder and error details. Suppresses duplicate alerts across restarts and optionally sends recovery messages. API outages and offline devices are logged without notifications.

## Install

Run these commands from the repository as the user who will run the monitor:

```bash
mkdir -p ~/.local/lib/syncover ~/.config/syncover ~/.config/systemd/user
install -m 644 syncover.py ~/.local/lib/syncover/syncover.py
install -m 644 systemd/syncover.service ~/.config/systemd/user/syncover.service
cp -n config.example.json ~/.config/syncover/config.json
chmod 600 ~/.config/syncover/config.json
```

Edit `~/.config/syncover/config.json`. Set device_name to Titan or Donnager, the local Syncthing API key (Settings → GUI), and your Pushover application token and user key. Both installations can use the same Pushover credentials. Keep credentials outside the repository.

```bash
python3 ~/.local/lib/syncover/syncover.py --test-notification
python3 ~/.local/lib/syncover/syncover.py --once
systemctl --user daemon-reload
systemctl --user enable --now syncover.service
journalctl --user -u syncover.service -f
```

For a headless server, enable operation without an active login:

```bash
sudo loginctl enable-linger "$USER"
```

After configuration changes: `systemctl --user restart syncover.service`.
To stop: `systemctl --user disable --now syncover.service`.
To update: repeat the two install commands, daemon-reload, and restart.

## Behavior

Folders are tracked independently. Changed errors start a fresh grace period, so rapidly changing errors can postpone an alert. Paused folders are skipped. Failed API requests preserve incident state. Recovery requires an idle folder with no reported errors; it means errors cleared, not that every remote device is up to date. Removed folders retain their last incident state without a recovery message.

Delivery failures retry on later polls. A lost response or a crash after sending but before saving can cause duplicates. Run one copy per local Syncthing instance. Error details and file paths are sent to Pushover. HTTPS certificates are verified; local Syncthing defaults to loopback HTTP.

## Development

```bash
python3 -m unittest discover -s tests -v
```

References: [Syncthing errors](https://docs.syncthing.net/rest/folder-errors-get.html), [folder status](https://docs.syncthing.net/rest/db-status-get.html), [Pushover API](https://pushover.net/api).
