import hashlib
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'docs/research/evidence/2026-09-27-guest-pid'


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


class GuestPidEvidenceTests(unittest.TestCase):
    def test_hashes_and_cleanup(self):
        hashes = read(BASE / 'bundle-sha256.json')
        self.assertEqual(set(hashes), {p.relative_to(BASE).as_posix() for p in BASE.rglob('*')
            if p.is_file() and p.name != 'bundle-sha256.json'})
        for name, digest in hashes.items():
            self.assertEqual(hashlib.sha256((BASE / name).read_bytes()).hexdigest(), digest, name)
        self.assertEqual((BASE / 'guest-pid-common/containers-after.txt').read_text(), '')

    def test_guest_rejection_is_not_host_exhaustion(self):
        for limit in [32, 64]:
            run = BASE / f'guest-pid-{limit}'
            row, = read(run / 'results.json')
            self.assertTrue(row['passed'])
            self.assertEqual(row['recovery_exec']['exit_code'], 0)
            self.assertEqual(row['recovery_exec']['stdout'], 'RECOVERY_EXEC_OK')
            limits = next(e for e in row['events'] if e['event'] == 'limits')
            self.assertEqual((limits['nproc_soft'], limits['nproc_hard']), (limit, limit))
            self.assertEqual(limits['raise_hard_limit'], 'ValueError')
            at_limit = next(e for e in row['events'] if e['event'] == 'at_limit')
            self.assertEqual(at_limit['failure']['errno'], 11)
            self.assertEqual(at_limit['guest_processes'], limit)
            samples = read(run / f"runsc-{row['cap']}-samples.json")
            self.assertTrue(all(s['pids.events'] == 'max 0' for s in samples))
            self.assertLess(max(int(s['pids.current']) for s in samples), row['cap'])

    def test_host_boundary_remains_failure(self):
        run = BASE / 'guest-pid-host'
        logs = [(p.read_text(encoding='utf-8')) for p in (BASE / 'guest-pid-common/runtime-logs').glob('*.boot.txt')]
        for row in read(run / 'results.json'):
            self.assertFalse(row['passed'])
            self.assertIsNone(row['guest_limit'])
            self.assertEqual(row['container_state']['ExitCode'], 2)
            self.assertFalse(row['container_state']['OOMKilled'])
            inspect = read(run / f"runsc-{row['cap']}-inspect.json")
            self.assertTrue(any(inspect['Id'] in log and 'panic:' in log for log in logs))
            samples = read(run / f"runsc-{row['cap']}-samples.json")
            self.assertIn('max 1', [s['pids.events'] for s in samples])
