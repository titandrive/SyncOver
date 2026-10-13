import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace
import install


class UninstallTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name)
        self.paths = ['.config/systemd/user/syncover.service', '.local/lib/syncover/syncover.py',
                      '.config/syncover/config.json', '.local/state/syncover/state.json']
        for name in self.paths:
            path = self.home / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('test')

    @patch('install.subprocess.run', return_value=SimpleNamespace(stdout='loaded\n'))
    @patch('install.run')
    def test_preserves_settings_and_stops_first(self, run, subprocess):
        install.uninstall(self.home, purge=False)
        self.assertFalse((self.home / self.paths[0]).exists())
        self.assertFalse((self.home / self.paths[1]).exists())
        self.assertTrue((self.home / self.paths[2]).exists())
        self.assertTrue((self.home / self.paths[3]).exists())
        self.assertEqual(run.call_args_list[0].args, ('systemctl', '--user', 'stop', 'syncover.service'))

    @patch('install.subprocess.run', return_value=SimpleNamespace(stdout='not-found\n'))
    @patch('install.run')
    def test_default_removes_settings_and_repeat(self, run, subprocess):
        extra = self.home / '.config/syncover/unrelated.txt'
        extra.write_text('keep')
        install.uninstall(self.home)
        install.uninstall(self.home)
        for name in self.paths:
            self.assertFalse((self.home / name).exists())
        self.assertTrue(extra.exists())

    @patch('install.subprocess.run', return_value=SimpleNamespace(stdout='loaded\n'))
    @patch('install.run', side_effect=OSError('cannot stop'))
    def test_stop_failure_preserves_files(self, run, subprocess):
        with self.assertRaises(OSError):
            install.uninstall(self.home)
        for name in self.paths:
            self.assertTrue((self.home / name).exists())
