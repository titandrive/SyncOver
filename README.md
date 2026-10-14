# SyncOver

Lightweight Linux monitor for local Syncthing sync errors, delivered through Pushover. Install on each device (Titan and Donnager). Python 3.9+; no third-party packages.

Checks folders every 60 seconds. Alerts after an unchanged error set persists for 120 seconds. Includes the device, folder and error details. Suppresses duplicate alerts across restarts and optionally sends recovery messages. API outages and offline devices are logged without notifications.

## Android (experimental Morphe patch)

A standalone [Morphe patch](android/README.md) adds native error/recovery notifications to **Syncthing-Fork 2.1.6.0**. It uses the existing app event stream, without a separate monitor service or Pushover keys. The Android patch is distributed separately from Docker releases, with tags beginning `android-`.

See the [Android instructions](android/README.md) for compatibility, build steps, and installation/signature considerations. It has passed state-machine tests and an APK patch/rebuild check; on-device notification delivery is not yet verified.

## Linux desktop installation (systemd)

On each machine, run as your normal user (without sudo):

```bash
git clone https://github.com/titandrive/SyncOver.git
cd SyncOver
python3 install.py
```

Already cloned it? Just run `python3 install.py` inside the SyncOver folder.

The installer asks for the device name, Syncthing address, and Pushover keys. It tries to find your local Syncthing API key automatically. Otherwise, copy it from Syncthing → Settings → General. Find your Pushover user key on your account dashboard and create an application for its application token. Both machines can share those Pushover credentials.

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

## Docker Compose

Enable Docker and have Docker Compose available on Unraid (for example through a Compose management plugin). Compose pulls the prebuilt release image from GitHub Container Registry. No local build is required.

Keep the source on persistent storage:

```bash
cd /mnt/user/appdata
git clone https://github.com/titandrive/SyncOver.git syncover-source
cd syncover-source
mkdir -p /mnt/user/appdata/syncover
cp -n .env.example .env
chmod 600 .env
```

Edit `.env` in the source folder and enter the three API keys. All settings are available there; Compose passes them into the container as environment variables. The supplied Compose file uses host networking: `127.0.0.1:8384` works if Syncthing exposes its GUI/API on Titan's port 8384. If your Syncthing container uses a different published host port, change that port in `SYNCOVER_SYNCTHING_URL`. If Syncthing has its own LAN IP, use that IP instead. SyncOver does not need access to your synced files or Syncthing's appdata.

Test and launch from the source folder:

```bash
docker compose pull
docker compose run --rm syncover --test-notification
docker compose run --rm syncover --once
docker compose up -d
```

Settings: `.env` in your source folder. Alert state: `/mnt/user/appdata/syncover/state.json`. The application lives inside the container. Logs: `docker compose logs -f`. Environment changes: `docker compose up -d --force-recreate`. Updates: `git pull`, `docker compose pull`, then `docker compose up -d`.

The restart policy starts it again when Docker starts unless you explicitly stopped it. Ensure Unraid starts Docker automatically. Compose does not publish any SyncOver ports; the monitor has no web UI.

Uninstall: `docker compose down`. This removes the container, leaving `.env` in your source folder and alert state in appdata. Delete `.env` and `/mnt/user/appdata/syncover/state.json` to remove those too. The source checkout remains separate.

### Titan: existing ionproxy network

Use `compose.titan.yaml` for Titan. It joins the existing external `ionproxy` network and connects to `http://syncthing:8384`. This matches Titan's Syncthing container, which is named `syncthing` and already joins `ionproxy`. No Caddy labels or web UI are needed.

For a Compose management UI, paste the contents of `compose.titan.yaml` and supply the three API key environment variables through your manager, or replace the `${...}` placeholders with your keys. The keys are supplied to the container through its environment. Alert history lives in `/mnt/user/appdata/syncover/state.json`.

For terminal use, put the keys in `.env` next to the Compose file:

```bash
docker compose -f compose.titan.yaml pull
docker compose -f compose.titan.yaml up -d
```

This variant uses `ghcr.io/titandrive/syncover:latest`; the generic `compose.yaml` pins a release version. `latest` advances with releases, but running containers only update when you pull and recreate/redeploy them.

Verify the running installation:

```bash
docker exec syncover python /app/syncover.py --test-notification
docker exec syncover python /app/syncover.py --once
docker logs --tail 30 syncover
```

The test should arrive in Pushover, and the one-shot check should say `Syncthing check completed successfully`. Afterward the background monitor stays quiet until an unchanged error set persists for two minutes. Each folder gets one alert for an unchanged incident, an updated alert after changed errors persist, and a recovery notice when errors clear. Paused folders, offline devices, and slow syncing do not trigger notifications.

## Environment and CLI settings

Every setting accepts a `SYNCOVER_` environment variable and a CLI flag:

| Environment | CLI |
| --- | --- |
| `SYNCOVER_DEVICE_NAME` | `--device-name` |
| `SYNCOVER_SYNCTHING_URL` | `--syncthing-url` |
| `SYNCOVER_SYNCTHING_API_KEY` | `--syncthing-api-key` |
| `SYNCOVER_PUSHOVER_TOKEN` | `--pushover-token` |
| `SYNCOVER_PUSHOVER_USER` | `--pushover-user` |
| `SYNCOVER_POLL_SECONDS` | `--poll-seconds` |
| `SYNCOVER_ERROR_DELAY_SECONDS` | `--error-delay-seconds` |
| `SYNCOVER_NOTIFY_RECOVERY` | `--notify-recovery` / `--no-notify-recovery` |
| `SYNCOVER_STATE_FILE` | `--state-file` |

Precedence: CLI flags → environment → optional JSON file → defaults. Environment booleans accept true/false, yes/no, or 1/0. Config files are optional when keys are supplied through environment or flags. CLI flags apply to that invocation; they do not save settings.

```bash
docker compose run --rm syncover --poll-seconds 90 --no-notify-recovery --once
python3 syncover.py --device-name Donnager --error-delay-seconds 180
```

The systemd installer continues to use its saved JSON configuration. Docker uses `.env`; no config.json is required. Custom state paths inside Docker must be under `/config` to persist. Keep `.env` private; it is excluded from Git and the Docker build context.

## Behavior

Folders are tracked independently. Changed errors start a fresh grace period, so rapidly changing errors can postpone an alert. Paused folders are skipped. Failed API requests preserve incident state. Recovery requires an idle folder with no reported errors; it means errors cleared, not that every remote device is up to date. Removed folders retain their last incident state without a recovery message.

Delivery failures retry on later polls. A lost response or a crash after sending but before saving can cause duplicates. Run one copy per local Syncthing instance. Error details and file paths are sent to Pushover. HTTPS certificates are verified; local Syncthing defaults to loopback HTTP.

## Development

```bash
python3 -m unittest discover -s tests -v
```

References: [Syncthing errors](https://docs.syncthing.net/rest/folder-errors-get.html), [folder status](https://docs.syncthing.net/rest/db-status-get.html), [Pushover API](https://pushover.net/api).
