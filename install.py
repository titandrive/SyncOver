#!/usr/bin/env python3
"""Interactive installer for SyncOver. Run as your normal Linux user."""
import argparse
import getpass
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import xml.etree.ElementTree as ET


def detected_key(home):
    for path in (home / '.local/state/syncthing/config.xml',
                 home / '.config/syncthing/config.xml'):
        try:
            return ET.parse(path).findtext('gui/apikey') or ''
        except (OSError, ET.ParseError):
            continue
    return ''


def ask(label, default='', secret=False):
    prompt = f'{label}' + (' [Enter to keep existing]' if secret and default else
                              f' [{default}]' if default else '') + ': '
    while True:
        value = (getpass.getpass(prompt) if secret else input(prompt)).strip() or default
        if value:
            return value
        print('Please enter a value.')


def run(*args):
    subprocess.run(args, check=True)


def uninstall(home, purge=False):
    """Remove this user's installation; leave source checkout and shared settings."""
    unit = home / '.config/systemd/user/syncover.service'
    loaded = subprocess.run(
        ['systemctl', '--user', 'show', 'syncover.service', '-p', 'LoadState', '--value'],
        capture_output=True, text=True)
    # Never remove files while an installed service could still be running.
    if loaded.stdout.strip() != 'not-found':
        run('systemctl', '--user', 'stop', 'syncover.service')
        run('systemctl', '--user', 'disable', 'syncover.service')
    unit.unlink(missing_ok=True)
    app_dir = home / '.local/lib/syncover'
    (app_dir / 'syncover.py').unlink(missing_ok=True)
    try:
        app_dir.rmdir()
    except FileNotFoundError:
        pass
    except OSError:
        print('Additional files in the application folder were preserved.')
    if purge:
        for directory, names in (
                (home / '.config/syncover', ('config.json', 'config.tmp')),
                (home / '.local/state/syncover', ('state.json', 'state.tmp'))):
            for name in names:
                (directory / name).unlink(missing_ok=True)
            try:
                directory.rmdir()
            except FileNotFoundError:
                pass
            except OSError:
                print(f'Additional files preserved in {directory}.')
    run('systemctl', '--user', 'daemon-reload')
    print('SyncOver uninstalled. Source checkout and user lingering settings were preserved.')
    if purge:
        print('Default configuration and alert history removed. Custom state paths are preserved.')
    else:
        print('Configuration and alert history preserved for reinstalling.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--uninstall', action='store_true', help='Stop and remove SyncOver')
    parser.add_argument('--purge', action='store_true', help='Also remove saved keys and default alert history')
    args = parser.parse_args()
    if args.purge and not args.uninstall:
        parser.error('--purge requires --uninstall')
    if sys.platform != 'linux' or os.geteuid() == 0:
        sys.exit('Run this installer on Linux as your normal user, without sudo.')
    if sys.version_info < (3, 9) or not shutil.which('systemctl'):
        sys.exit('SyncOver needs Python 3.9+ and systemd.')
    # Check before writing files, so a missing user session has a clear error.
    result = subprocess.run(['systemctl', '--user', 'show-environment'],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if result.returncode:
        sys.exit('Cannot reach your user service manager. Log in directly as your normal user and retry.')
    home = Path.home()
    if args.uninstall:
        uninstall(home, args.purge)
        return
    source = Path(__file__).resolve().parent
    config_path = home / '.config/syncover/config.json'
    config = json.loads((source / 'config.example.json').read_text())
    if config_path.exists():
        config.update(json.loads(config_path.read_text()))
    else:
        config['device_name'] = socket.gethostname()
    print('\nSyncOver setup — install on each machine running Syncthing.\n')
    config['device_name'] = ask('Device name', config['device_name'])
    config['syncthing_url'] = ask('Syncthing address', config['syncthing_url'])
    for key, label in (('syncthing_api_key', 'Syncthing API key (Settings → GUI)'),
                       ('pushover_token', 'Pushover application token'),
                       ('pushover_user', 'Pushover user key')):
        default = config.get(key, '')
        if default.startswith('REPLACE_'):
            default = detected_key(home) if key == 'syncthing_api_key' else ''
        config[key] = ask(label, default, secret=True)
    os.umask(0o077)
    config_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = config_path.with_suffix('.tmp')
    temporary.write_text(json.dumps(config, indent=2) + '\n')
    temporary.chmod(0o600)
    temporary.replace(config_path)
    app = home / '.local/lib/syncover/syncover.py'
    unit = home / '.config/systemd/user/syncover.service'
    for target, origin in ((app, source / 'syncover.py'),
                           (unit, source / 'systemd/syncover.service')):
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(origin, target)
    # Use the interpreter that launched setup, including installations outside /usr/bin.
    unit.write_text(unit.read_text().replace('/usr/bin/python3', '"' + sys.executable + '"'))
    print('\nSending a Pushover test notification…')
    run(sys.executable, str(app), '--test-notification')
    print('Checking Syncthing…')
    run(sys.executable, str(app), '--once')
    run('systemctl', '--user', 'daemon-reload')
    run('systemctl', '--user', 'enable', '--now', 'syncover.service')
    run('systemctl', '--user', 'restart', 'syncover.service')
    print('\nSyncOver is running. Your keys are saved privately outside the repository.')
    linger = subprocess.run(['loginctl', 'show-user', getpass.getuser(), '-p', 'Linger', '--value'],
                            capture_output=True, text=True)
    if linger.stdout.strip() != 'yes':
        if input('Keep SyncOver running after logout (useful on servers)? [y/N]: ').strip().lower() in ('y', 'yes'):
            run('sudo', 'loginctl', 'enable-linger', getpass.getuser())
    print('Status: systemctl --user status syncover')


if __name__ == '__main__':
    try:
        main()
    except (KeyboardInterrupt, EOFError):
        sys.exit('\nSetup cancelled.')
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        sys.exit(f'Operation did not finish ({type(exc).__name__}). Fix the reported issue and run the installer again.')
