import json
import pathlib
import subprocess
import sys
import unittest

HELPER = pathlib.Path(__file__).parent / 'container-e2e/receipt_diagnostic.py'


class ReceiptDiagnosticTests(unittest.TestCase):
    def test_partial_cause_is_preserved_without_sensitive_fields(self):
        self.assertTrue(HELPER.is_file(), 'Missing bounded receipt diagnostic helper')
        value = {'summary': {'outcome': 'partial'}, 'receipt': {
            'outcome': 'partial', 'exit_code': 1, 'argv': ['do-not-export-argv'],
            'steps': [{'name': 'python_dependencies', 'ok': False, 'detail': 'wheel validation failed'},
                      {'name': 'auth', 'ok': False, 'detail': 'password=do-not-export-value'}],
            'skips': [{'name': 'restart', 'reason': 'externally supervised'}],
            'gateway_restart': {'incomplete': True, 'phase_error': 'restart failed',
                                'credential': 'do-not-export-credential'},
            'fleet': [{'profile': 'do-not-export-profile', 'state': 'stale'}]}}
        result = subprocess.run([sys.executable, '-I', str(HELPER)],
                                input=json.dumps(value), text=True, capture_output=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        self.assertEqual(data['outcome'], 'partial')
        self.assertEqual(data['steps'][0]['detail'], 'wheel validation failed')
        self.assertIs(data['steps'][0]['ok'], False)
        self.assertEqual(data['steps'][1]['detail'], '[REDACTED]')
        self.assertEqual(data['gateway_restart']['phase_error'], 'restart failed')
        self.assertEqual(data['fleet_states'], ['stale'])
        self.assertNotIn('do-not-export', result.stdout)
        self.assertNotIn('argv', data)

    def test_malformed_and_large_fields_stay_bounded(self):
        for value in ([], {'receipt': {'steps': [{'name': 'x', 'ok': False, 'detail': 'x' * 5000}] * 120,
                                     'fleet': [{'state': 3}, {'state': 'current'}]},
                          'action_status': {'lines': ['line'] * 100}}):
            with self.subTest(kind=type(value).__name__):
                result = subprocess.run([sys.executable, '-I', str(HELPER)],
                                        input=json.dumps(value), text=True, capture_output=True, timeout=15)
                self.assertEqual(result.returncode, 0, result.stderr)
                data = json.loads(result.stdout)
                self.assertLessEqual(len(data['steps']), 80)
                self.assertTrue(all(len(row['detail'] or '') <= 1200 for row in data['steps']))
                self.assertLessEqual(len(data['action_log_tail']), 60)


if __name__ == '__main__':
    unittest.main()
