"""A fake secret planted in every output shape must not reach the published bundle."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location(
    'publisher', Path(__file__).with_name('gvisor-publish-evidence.py'))
publisher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(publisher)
Redactor = publisher.redact_module.Redactor

# Deliberately matches no built-in shape, so only registration can catch it.
SECRET = 'PLANTED-fake-credential-8842-not-real'


def build(raw):
    """One file per way this project actually produces evidence."""
    (raw / 'runtime-logs').mkdir(parents=True)
    # Matrix.log output.
    (raw / 'E05.jsonl').write_text(
        json.dumps({'command': ['claude', '--key', SECRET], 'stdout': 'ok'}) + '\n'
        + json.dumps({'stdout': f'used {SECRET}'}) + '\n')
    # Matrix.write output, including a secret-named field with an opaque value.
    (raw / 'report.json').write_text(json.dumps(
        {'environment': {'claude': '2.1.283', 'api_key': 'opaque-but-sensitive-value'},
         'note': f'ran with {SECRET}'}, indent=2))
    # PID runner writes these by piping subprocess stdout straight to a file.
    (raw / 'runsc-64-shell.txt').write_text(f'SHELL_READY\nenv: ANTHROPIC_API_KEY={SECRET}\n')
    (raw / 'runsc-64-probe.txt').write_text(f'{{"event": "at_limit"}}\ntoken {SECRET}\n')
    # runsc writes its own debug logs; they never pass through the harness.
    (raw / 'runtime-logs' / 'runsc.log.boot.txt').write_text(f'D0927 boot arg={SECRET}\n')
    (raw / 'kernel.log').write_text(f'cgroup: fork rejected; ctx={SECRET}\n')
    # A non-text artifact cannot be masked, only reported.
    (raw / 'screenshot.png').write_bytes(b'\x89PNG\r\n\x1a\n binary')


class PublishTests(unittest.TestCase):
    def publish(self, secrets=(SECRET,)):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        base = Path(directory.name)
        raw, out = base / 'raw', base / 'out'
        raw.mkdir()
        build(raw)
        out.mkdir()
        report = publisher.publish(raw, out, Redactor(secrets))
        return out, report

    def test_no_published_file_contains_the_secret(self):
        out, report = self.publish()
        for path in out.rglob('*'):
            if path.is_file():
                self.assertNotIn(SECRET, path.read_bytes().decode('utf-8', 'replace'), msg=str(path))
        self.assertEqual(report['leaks'], [])
        self.assertEqual(report['files'], 7)

    def test_every_evidence_shape_is_covered_including_nested_and_raw_text(self):
        out, _ = self.publish()
        for name in ('E05.jsonl', 'report.json', 'runsc-64-shell.txt', 'runsc-64-probe.txt',
                     'runtime-logs/runsc.log.boot.txt', 'kernel.log'):
            with self.subTest(name=name):
                self.assertIn(publisher.redact_module.MASK, (out / name).read_text())

    def test_secret_named_json_field_is_masked_even_without_a_known_shape(self):
        out, _ = self.publish()
        published = json.loads((out / 'report.json').read_text())
        self.assertEqual(published['environment']['api_key'], publisher.redact_module.MASK)
        self.assertEqual(published['environment']['claude'], '2.1.283')

    def test_jsonl_stays_parseable_after_scrubbing(self):
        out, _ = self.publish()
        lines = [json.loads(line) for line in (out / 'E05.jsonl').read_text().splitlines() if line.strip()]
        self.assertEqual(len(lines), 2)
        self.assertEqual(lines[0]['command'][0], 'claude')
        self.assertEqual(lines[0]['stdout'], 'ok')

    def test_binary_is_copied_untouched_and_reported(self):
        out, report = self.publish()
        self.assertEqual(report['binary'], ['screenshot.png'])
        self.assertEqual((out / 'screenshot.png').read_bytes(), b'\x89PNG\r\n\x1a\n binary')

    def test_hashes_describe_the_published_bytes_not_the_raw_ones(self):
        out, report = self.publish()
        import hashlib
        recorded = json.loads((out / publisher.HASH_FILE).read_text())
        self.assertEqual(set(recorded), set(report['hashes']))
        for name, digest in recorded.items():
            self.assertEqual(hashlib.sha256((out / name).read_bytes()).hexdigest(), digest)

    def test_a_surviving_secret_is_reported_as_a_leak(self):
        # Simulate a format this tool cannot mask: the secret sits in a binary file.
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        base = Path(directory.name)
        raw, out = base / 'raw', base / 'out'
        raw.mkdir()
        out.mkdir()
        (raw / 'core.dump').write_bytes(b'\x00\x01' + SECRET.encode() + b'\xff')
        report = publisher.publish(raw, out, Redactor([SECRET]))
        self.assertEqual([leak['file'] for leak in report['leaks']], ['core.dump'])
