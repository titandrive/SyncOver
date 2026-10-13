import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from syncover import load_config


class ConfigTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / 'config.json'
        self.env = {'SYNCOVER_SYNCTHING_API_KEY': 'test', 'SYNCOVER_PUSHOVER_TOKEN': 'test',
                    'SYNCOVER_PUSHOVER_USER': 'test'}

    def test_env_only_all_settings(self):
        values = dict(self.env, SYNCOVER_DEVICE_NAME='Titan', SYNCOVER_SYNCTHING_URL='http://localhost:8385',
                      SYNCOVER_POLL_SECONDS='90', SYNCOVER_ERROR_DELAY_SECONDS='180',
                      SYNCOVER_NOTIFY_RECOVERY='false', SYNCOVER_STATE_FILE='/config/state.json')
        with patch.dict(os.environ, values, clear=True):
            config = load_config(self.path)
        self.assertEqual(config['device_name'], 'Titan')
        self.assertEqual(config['poll_seconds'], 90)
        self.assertEqual(config['error_delay_seconds'], 180)
        self.assertFalse(config['notify_recovery'])
        self.assertEqual(config['state_file'], '/config/state.json')
        self.assertEqual(config['syncthing_url'], 'http://localhost:8385')

    def test_precedence(self):
        self.path.write_text('{"device_name": "file", "poll_seconds": 60}')
        with patch.dict(os.environ, dict(self.env, SYNCOVER_DEVICE_NAME='env', SYNCOVER_POLL_SECONDS='90'), clear=True):
            config = load_config(self.path, {'device_name': 'cli', 'notify_recovery': False})
        self.assertEqual(config['device_name'], 'cli')
        self.assertEqual(config['poll_seconds'], 90)
        self.assertFalse(config['notify_recovery'])

    def test_invalid_boolean(self):
        with patch.dict(os.environ, dict(self.env, SYNCOVER_NOTIFY_RECOVERY='maybe'), clear=True):
            with self.assertRaises(ValueError):
                load_config(self.path)
