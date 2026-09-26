"""Synthetic reports verify the gate, never stand in for Linux evidence."""
import copy
import hashlib
import importlib.util
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).with_name("gvisor-report.py")
spec = importlib.util.spec_from_file_location("report", SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class ReportTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        (self.root / "synthetic.log").write_text("synthetic test fixture\n")
        self.evidence = [{"path": "synthetic.log", "sha256": hashlib.sha256(
            (self.root / "synthetic.log").read_bytes()).hexdigest()}]

    def complete(self):
        report = module.template()
        report["environment"] = {key: "test-only" for key in module.ENV_FIELDS}
        report["environment"]["image_pin"] = "sha256:" + "a" * 64
        report["preflight"] = {"verdict": "ready_for_manual_matrix_not_go", "evidence": self.evidence}
        for row in report["cases"]:
            row.update(status="pass", started_at="2026-09-26T10:00:00Z",
                       finished_at="2026-09-26T10:01:00Z", command="synthetic",
                       exit_code=0, expected="synthetic", observed="synthetic",
                       claude_before="test-only", claude_after="test-only", evidence=self.evidence)
        report["cleanup"] = {"status": "verified", "evidence": self.evidence}
        return report

    def test_unexecuted_template_cannot_pass(self):
        result, code = module.check(module.template(), self.root)
        self.assertEqual(code, 2)
        self.assertEqual(result["status"], "incomplete")

    def test_complete_bundle_is_only_ready_for_review(self):
        report = self.complete()
        report["cases"][7]["exit_code"] = 137  # Expected memory-limit termination.
        result, code = module.check(report, self.root)
        self.assertEqual(code, 0)
        self.assertEqual(result["status"], "ready_for_review")
        self.assertFalse(result["runtime_go"])

    def test_recorded_failure_is_not_success(self):
        report = self.complete()
        report["cases"][5]["status"] = "fail"
        result, code = module.check(report, self.root)
        self.assertEqual((result["status"], code), ("failures_recorded", 1))

    def test_missing_duplicate_case_or_version_drift_blocks(self):
        for mutate in (lambda r: r["cases"].pop(),
                       lambda r: r["cases"].append(copy.deepcopy(r["cases"][0])),
                       lambda r: r["cases"][0].update(claude_after="changed"),
                       lambda r: r["cases"][0].update(finished_at="2026-09-26T09:59:00Z"),
                       lambda r: r["environment"].update(image_pin="image:latest")):
            report = self.complete()
            mutate(report)
            self.assertEqual(module.check(report, self.root)[1], 2)

    def test_missing_modified_or_escaping_evidence_blocks(self):
        for path in ("missing.log", "../outside.log", str(self.root / "synthetic.log")):
            report = self.complete()
            report["cases"][0]["evidence"] = [{**self.evidence[0], "path": path}]
            self.assertEqual(module.check(report, self.root)[1], 2)
        (self.root / "synthetic.log").write_text("changed after hashing")
        self.assertEqual(module.check(self.complete(), self.root)[1], 2)

    def test_init_preserves_existing_report_and_bad_json_is_safe(self):
        target = self.root / "report.json"
        command = [sys.executable, "-B", str(SCRIPT), "--init", str(target)]
        self.assertEqual(subprocess.run(command, capture_output=True).returncode, 0)
        original = target.read_bytes()
        self.assertEqual(subprocess.run(command, capture_output=True).returncode, 2)
        self.assertEqual(target.read_bytes(), original)
        target.write_text("SECRET INVALID JSON")
        result = subprocess.run([sys.executable, "-B", str(SCRIPT), "--check", str(target)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        self.assertNotIn("SECRET", result.stdout + result.stderr)

    def test_symlink_to_real_external_evidence_is_rejected(self):
        with tempfile.TemporaryDirectory() as outside:
            target = Path(outside) / "valid.log"
            target.write_text("synthetic test fixture\n")
            (self.root / "escape.log").symlink_to(target)
            report = self.complete()
            report["cases"][0]["evidence"] = [{**self.evidence[0], "path": "escape.log"}]
            self.assertEqual(module.check(report, self.root)[1], 2)


if __name__ == "__main__":
    unittest.main()
