"""Validate published bytes and preserve the distinction between partial and go."""
import hashlib
import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT / 'docs/research/evidence/2026-09-27-no-key'
spec = importlib.util.spec_from_file_location('report', ROOT / 'scripts/gvisor-report.py')
report_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(report_module)


class PublishedEvidenceTests(unittest.TestCase):
    def test_all_published_files_retain_recorded_hashes(self):
        manifest = json.loads((BUNDLE / 'bundle-sha256.json').read_text(encoding='utf-8'))
        actual = {p.name for p in BUNDLE.iterdir() if p.is_file() and p.name != 'bundle-sha256.json'}
        self.assertEqual(set(manifest), actual)
        for name, digest in manifest.items():
            self.assertEqual(Path(name).name, name)
            self.assertEqual(hashlib.sha256((BUNDLE / name).read_bytes()).hexdigest(), digest, name)

    def test_partial_runtime_evidence_cannot_become_go(self):
        report = json.loads((BUNDLE / 'report.json').read_text(encoding='utf-8'))
        result, code = report_module.check(report, BUNDLE)
        self.assertEqual(code, 2)
        self.assertEqual(result['status'], 'incomplete')
        self.assertFalse(result['runtime_go'])
        self.assertEqual(result['problems'], ['case[4]: not executed', 'case[9]: not executed'])
        self.assertEqual([r['id'] for r in report['cases'] if r['status'] == 'fail'], ['E09'])


if __name__ == '__main__':
    unittest.main()
