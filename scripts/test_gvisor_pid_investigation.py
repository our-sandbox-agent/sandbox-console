"""Every acceptance condition must be load-bearing: drop one and the case fails."""
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('pid_runner', Path(__file__).with_name('gvisor-pid-investigation.py'))
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)

PASSING = {
    'probe_exit': 0,
    'state': {'Running': True},
    'guard': None,
    'events': [{'rejected_eagain': True}, {'progress': True}],
    'shell_text': 'SHELL_AT_LIMIT_OK\nSHELL_AFTER_OK\n',
    'recovery': {'exit_code': 0, 'stdout': 'RECOVERY_EXEC_OK'},
}


def evaluate(**overrides):
    values = dict(PASSING, **overrides)
    return runner.case_passed(values['probe_exit'], values['state'], values['guard'],
                              values['events'], values['shell_text'], values['recovery'])


class AcceptanceTests(unittest.TestCase):
    def test_all_conditions_met_passes(self):
        self.assertTrue(evaluate())

    def test_probe_must_exit_zero(self):
        # The observed runsc failure exits 128 while the sandbox dies.
        for probe_exit in (128, 1, 2, 124):
            with self.subTest(probe_exit=probe_exit):
                self.assertFalse(evaluate(probe_exit=probe_exit))

    def test_container_must_still_be_running(self):
        # This is the whole point: rejecting a fork must not kill the sandbox.
        self.assertFalse(evaluate(state={'Running': False}))

    def test_a_fired_guard_cannot_pass(self):
        for guard in ('headroom', 'deadline'):
            with self.subTest(guard=guard):
                self.assertFalse(evaluate(guard=guard))

    def test_rejection_must_be_eagain(self):
        self.assertFalse(evaluate(events=[{'progress': True}]))
        self.assertFalse(evaluate(events=[{'rejected_eagain': False, 'errno': 12}, {'progress': True}]))

    def test_existing_worker_must_keep_progressing(self):
        self.assertFalse(evaluate(events=[{'rejected_eagain': True}]))
        self.assertFalse(evaluate(events=[]))

    def test_existing_shell_must_respond_at_limit_and_after(self):
        for shell_text in ('', 'SHELL_AT_LIMIT_OK\n', 'SHELL_AFTER_OK\n', 'unrelated output\n'):
            with self.subTest(shell_text=shell_text.strip()):
                self.assertFalse(evaluate(shell_text=shell_text))

    def test_recovery_exec_must_succeed_with_exact_marker(self):
        for recovery in (None, {'exit_code': 1, 'stdout': 'RECOVERY_EXEC_OK'},
                         {'exit_code': 0, 'stdout': ''},
                         {'exit_code': 0, 'stdout': 'RECOVERY_EXEC_OK extra'}):
            with self.subTest(recovery=recovery):
                self.assertFalse(evaluate(recovery=recovery))
