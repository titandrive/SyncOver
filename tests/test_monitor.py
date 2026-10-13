import tempfile
import unittest
from pathlib import Path
from syncover import Monitor


class MonitorTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.messages = []
        self.config = {'state_file': str(Path(self.tmp.name) / 'state.json'),
                       'device_name': 'Titan', 'error_delay_seconds': 120, 'notify_recovery': True}
        self.monitor = Monitor(self.config, lambda *args: self.messages.append(args))

    def test_grace_dedup_restart_recovery(self):
        for now in (0, 60, 120, 180):
            self.monitor.observe('docs', 'Documents', ['file: denied'], now)
        self.assertEqual(len(self.messages), 1)
        self.assertIn('Titan', self.messages[0][0])
        restarted = Monitor(self.config, lambda *args: self.messages.append(args))
        restarted.observe('docs', 'Documents', ['file: denied'], 240)
        self.assertEqual(len(self.messages), 1)
        restarted.observe('docs', 'Documents', [], 300)
        restarted.observe('docs', 'Documents', [], 360)
        self.assertEqual(len(self.messages), 2)

    def test_transient_silent(self):
        self.monitor.observe('docs', 'Documents', ['failed'], 0)
        self.monitor.observe('docs', 'Documents', [], 60)
        self.assertEqual(self.messages, [])

    def test_send_failure_retries(self):
        self.monitor.observe('docs', 'Documents', ['failed'], 0)
        def fail(*args):
            raise OSError('delivery failed')
        self.monitor.send = fail
        with self.assertRaises(OSError):
            self.monitor.observe('docs', 'Documents', ['failed'], 120)
        self.monitor.send = lambda *args: self.messages.append(args)
        self.monitor.observe('docs', 'Documents', ['failed'], 180)
        self.assertEqual(len(self.messages), 1)

    def test_offline_keeps_incident(self):
        self.monitor.observe('docs', 'Documents', ['failed'], 0)
        self.monitor.observe('docs', 'Documents', ['failed'], 120)
        def api(endpoint, **kwargs):
            if endpoint == 'config/folders':
                return [{'id': 'docs'}]
            raise OSError('offline')
        self.monitor.api = api
        self.monitor.poll()
        self.assertIn('docs', self.monitor.state)
        self.assertEqual(len(self.messages), 1)

    def test_retry_is_not_recovery(self):
        self.monitor.observe('docs', 'Documents', ['failed'], 0)
        self.monitor.observe('docs', 'Documents', ['failed'], 120)
        self.monitor.api = lambda endpoint, **kwargs: {'config/folders': [{'id': 'docs'}],
            'folder/errors': {'errors': []}, 'db/status': {'state': 'syncing'}}[endpoint]
        self.monitor.poll()
        self.assertEqual(len(self.messages), 1)
        self.assertIn('docs', self.monitor.state)

    def test_changed_error_delayed(self):
        self.monitor.observe('docs', 'Documents', ['a'], 0)
        self.monitor.observe('docs', 'Documents', ['a'], 120)
        self.monitor.observe('docs', 'Documents', ['b'], 180)
        self.assertEqual(len(self.messages), 1)
        self.monitor.observe('docs', 'Documents', ['b'], 300)
        self.assertEqual(len(self.messages), 2)

    def test_null_errors_are_healthy_and_resolve_incident(self):
        self.monitor.observe('docs', 'Documents', ['failed'], 0)
        self.monitor.observe('docs', 'Documents', ['failed'], 120)
        self.monitor.api = lambda endpoint, **kwargs: {
            'config/folders': [{'id': 'docs'}],
            'folder/errors': {'errors': None},
            'db/status': {'state': 'idle', 'pullErrors': 0}}[endpoint]
        self.monitor.poll()
        self.assertNotIn('docs', self.monitor.state)
        self.assertEqual(len(self.messages), 2)

    def test_null_errors_during_retry_do_not_resolve(self):
        self.monitor.observe('docs', 'Documents', ['failed'], 0)
        self.monitor.observe('docs', 'Documents', ['failed'], 120)
        self.monitor.api = lambda endpoint, **kwargs: {
            'config/folders': [{'id': 'docs'}],
            'folder/errors': {'errors': None},
            'db/status': {'state': 'syncing', 'pullErrors': 0}}[endpoint]
        self.monitor.poll()
        self.assertIn('docs', self.monitor.state)
        self.assertEqual(len(self.messages), 1)
