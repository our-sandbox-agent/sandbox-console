import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('pid_runner', Path(__file__).with_name('gvisor-pid-investigation.py'))
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


class RecoveryAcceptanceTests(unittest.TestCase):
    def evaluate(self, recovery):
        return runner.case_passed(0, {'Running': True}, None,
            [{'rejected_eagain': True}, {'progress': True}],
            'SHELL_AT_LIMIT_OK\nSHELL_AFTER_OK\n', recovery)

    def test_successful_recovery_passes(self):
        self.assertTrue(self.evaluate({'exit_code': 0, 'stdout': 'RECOVERY_EXEC_OK'}))

    def test_failed_recovery_fails_even_when_existing_work_survives(self):
        self.assertFalse(self.evaluate({'exit_code': 1, 'stdout': 'RECOVERY_EXEC_OK'}))

    def test_missing_or_wrong_recovery_output_fails(self):
        for recovery in [None, {'exit_code': 0, 'stdout': ''},
                         {'exit_code': 0, 'stdout': 'RECOVERY_EXEC_OK extra'}]:
            with self.subTest(recovery=recovery):
                self.assertFalse(self.evaluate(recovery))
