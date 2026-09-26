"""Verify evidence integrity and cross-check the PID investigation's claims."""
import hashlib
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / 'docs/research/evidence/2026-09-27-pid'


class PidEvidenceTests(unittest.TestCase):
    def test_bundle_integrity(self):
        hashes = json.loads((EVIDENCE / 'bundle-sha256.json').read_text())
        actual = {p.relative_to(EVIDENCE).as_posix() for p in EVIDENCE.rglob('*')
                  if p.is_file() and p.name != 'bundle-sha256.json'}
        self.assertEqual(set(hashes), actual)
        for name, digest in hashes.items():
            self.assertEqual(hashlib.sha256((EVIDENCE / name).read_bytes()).hexdigest(), digest, name)

    def test_six_cases_and_failure_attribution(self):
        rows = json.loads((EVIDENCE / 'results.json').read_text())
        self.assertEqual({(r['runtime'], r['cap']) for r in rows},
                         {(r, c) for r in ['runsc', 'runc'] for c in [64, 128, 256]})
        for row in rows:
            name = f"{row['runtime']}-{row['cap']}"
            inspect = json.loads((EVIDENCE / (name + '-inspect.json')).read_text())
            self.assertFalse(inspect['State']['OOMKilled'])
            samples = json.loads((EVIDENCE / (name + '-samples.json')).read_text())
            self.assertIn('max 1', [s['pids.events'] for s in samples])
            self.assertGreaterEqual(min(s['host_available_mib'] for s in samples), 2048)
            self.assertIn(inspect['Id'], (EVIDENCE / 'kernel.log').read_text())
            if row['runtime'] == 'runsc':
                self.assertFalse(row['passed'])
                self.assertEqual(inspect['State']['ExitCode'], 2)
                self.assertFalse(inspect['State']['Running'])
                logs = [p.read_text(encoding='utf-8') for p in (EVIDENCE / 'runtime-logs').glob('*.boot.txt')]
                self.assertTrue(any(inspect['Id'] in log and 'panic: Unknown syscall 56' in log for log in logs))
            else:
                self.assertTrue(row['passed'])
                self.assertTrue(inspect['State']['Running'])
                records = [json.loads(line) for line in (EVIDENCE / (name + '.jsonl')).read_text().splitlines()]
                self.assertTrue(any(r.get('stdout') == 'RECOVERY_EXEC_OK' and r['exit_code'] == 0 for r in records))


if __name__ == '__main__':
    unittest.main()
