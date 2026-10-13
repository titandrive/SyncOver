#!/usr/bin/env python3
"""Syncthing error notifications. Python 3.9+, standard library only."""
import argparse
import hashlib
import json
import logging
import os
from pathlib import Path
import signal
import socket
import threading
import time
import urllib.parse
import urllib.request


def request(url, headers=None, data=None):
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers or {}, data=data), timeout=15) as response:
        return json.load(response)


class Monitor:
    def __init__(self, config, send=None):
        self.config = config
        self.path = Path(config['state_file']).expanduser()
        try:
            self.state = json.loads(self.path.read_text())
        except FileNotFoundError:
            self.state = {}
        self.send = send or self.notify

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix('.tmp')
        temporary.write_text(json.dumps(self.state))
        temporary.chmod(0o600)
        temporary.replace(self.path)

    def api(self, endpoint, **parameters):
        url = self.config['syncthing_url'].rstrip('/') + '/rest/' + endpoint
        if parameters:
            url += '?' + urllib.parse.urlencode(parameters)
        return request(url, {'X-API-Key': self.config['syncthing_api_key']})

    def notify(self, title, message):
        data = urllib.parse.urlencode({'token': self.config['pushover_token'],
            'user': self.config['pushover_user'], 'title': title[:250],
            'message': message[:1024], 'priority': 0}).encode()
        if request('https://api.pushover.net/1/messages.json', data=data).get('status') != 1:
            raise RuntimeError('Pushover rejected notification')

    def observe(self, folder, label, errors, now):
        current = self.state.get(folder)
        title = f"SyncOver · {self.config['device_name']} · {label}"
        if not errors:
            if current and current['notified'] and self.config['notify_recovery']:
                self.send(title, 'Syncthing errors cleared.')
            self.state.pop(folder, None)
            self.save()
            return
        errors = sorted(set(errors))
        fingerprint = hashlib.sha256(json.dumps(errors).encode()).hexdigest()
        if not current or current['fingerprint'] != fingerprint:
            current = {'fingerprint': fingerprint, 'since': now, 'sent': False,
                       'notified': bool(current and current['notified'])}
            self.state[folder] = current
        if not current['sent'] and now - current['since'] >= self.config['error_delay_seconds']:
            self.send(title, f"Syncthing reports {len(errors)} error(s):\n" + '\n'.join(errors))
            current['sent'] = current['notified'] = True
        self.save()

    def poll(self):
        for folder in self.api('config/folders'):
            if folder.get('paused'):
                continue
            fid = folder['id']
            try:
                errors, page = [], 1
                while True:
                    entries = self.api('folder/errors', folder=fid, page=page, perpage=100)['errors']
                    errors.extend(f"{e.get('path', '(folder)')}: {e['error']}" for e in entries)
                    if len(entries) < 100:
                        break
                    page += 1
                status = self.api('db/status', folder=fid)
                if status.get('state') == 'error':
                    errors.append(status.get('error') or 'Folder is in an error state')
                if status.get('pullErrors', 0) and not errors:
                    errors.append(f"{status['pullErrors']} item(s) failed to sync")
                # Retry cycles can temporarily clear errors; require idle for recovery.
                if not errors and status.get('state') != 'idle':
                    continue
                self.observe(fid, folder.get('label') or fid, errors, time.time())
            except Exception as exc:
                logging.warning('Folder %s check failed (%s); retaining state', fid, type(exc).__name__)
                if self.config.get('once'):
                    raise


def load_config(path, overrides=None):
    config = {'device_name': socket.gethostname(), 'syncthing_url': 'http://127.0.0.1:8384',
              'poll_seconds': 60, 'error_delay_seconds': 120, 'notify_recovery': True,
              'state_file': '~/.local/state/syncover/state.json'}
    config_path = Path(path).expanduser()
    if config_path.exists():
        config.update(json.loads(config_path.read_text()))
    settings = ('device_name', 'syncthing_url', 'syncthing_api_key', 'pushover_token',
                'pushover_user', 'poll_seconds', 'error_delay_seconds', 'notify_recovery', 'state_file')
    for key in settings:
        value = os.environ.get('SYNCOVER_' + key.upper())
        if value is not None:
            if key in ('poll_seconds', 'error_delay_seconds'):
                value = float(value)
            elif key == 'notify_recovery':
                if value.lower() not in ('true', 'false', '1', '0', 'yes', 'no'):
                    raise ValueError('SYNCOVER_NOTIFY_RECOVERY must be true or false')
                value = value.lower() in ('true', '1', 'yes')
            config[key] = value
    config.update({key: value for key, value in (overrides or {}).items()
                   if key in settings and value is not None})
    for key in ('syncthing_api_key', 'pushover_token', 'pushover_user'):
        if not isinstance(config.get(key), str) or not config[key].strip() or config[key].startswith('REPLACE_'):
            raise ValueError(f'Set {key} in configuration')
    for key, minimum in (('poll_seconds', 30), ('error_delay_seconds', 0)):
        if isinstance(config[key], bool) or not isinstance(config[key], (int, float)) or config[key] < minimum:
            raise ValueError(f'{key} must be a number >= {minimum}')
    if not isinstance(config['notify_recovery'], bool):
        raise ValueError('notify_recovery must be true or false')
    return config


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', default='~/.config/syncover/config.json')
    for name in ('device-name', 'syncthing-url', 'syncthing-api-key', 'pushover-token',
                 'pushover-user', 'state-file'):
        parser.add_argument('--' + name)
    parser.add_argument('--poll-seconds', type=float)
    parser.add_argument('--error-delay-seconds', type=float)
    parser.add_argument('--notify-recovery', action=argparse.BooleanOptionalAction, default=None)
    parser.add_argument('--once', action='store_true')
    parser.add_argument('--test-notification', action='store_true')
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
    os.umask(0o077)
    try:
        config = load_config(args.config, vars(args))
        config['once'] = args.once
        monitor = Monitor(config)
    except (ValueError, OSError) as exc:
        parser.error(str(exc))
    if args.test_notification:
        monitor.notify(f"SyncOver · {config['device_name']}", 'Pushover notifications are working.')
        return 0
    stop = threading.Event()
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda *_: stop.set())
    logging.info('Monitoring local Syncthing on %s', config['device_name'])
    while not stop.is_set():
        try:
            monitor.poll()
        except Exception as exc:
            logging.warning('Check failed (%s); no offline notification sent', type(exc).__name__)
            if args.once:
                return 1
        if args.once:
            return 0
        stop.wait(config['poll_seconds'])
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
