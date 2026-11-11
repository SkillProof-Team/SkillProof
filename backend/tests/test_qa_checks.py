"""Test the CI runner and the Issue check in isolated sample directories."""

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
EXISTING = "test_sample.ExistingTests.test_existing"
OTHER = "test_sample.ExistingTests.test_other"


class QACheckTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.registrations = self.root / "tests" / "acceptance" / "issues"
        self.registrations.mkdir(parents=True)
        self.backend = self.root / "backend" / "tests"
        self.backend.mkdir(parents=True)
        self.pr = self.root / "pr.json"
        self.pr.write_text(json.dumps({"body": "Refs #7"}))
        self.changed = self.root / "changed"
        self.changed.write_bytes(b"backend/app/main.py\0")
        self.output = self.root / "output"
        self.env = {
            **os.environ,
            "PR_DETAILS": str(self.pr),
            "GITHUB_OUTPUT": str(self.output),
            "CHANGED_FILES": str(self.changed),
            "FRONTEND_RESULT": "success",
            "BACKEND_RESULT": "success",
            "PASSED_TESTS": json.dumps([EXISTING]),
            "PYTHONDONTWRITEBYTECODE": "1",
        }

    def register(self, ids, issue=7):
        (self.registrations / f"{issue}.json").write_text(json.dumps({"required_tests": ids}))

    def run_script(self, name):
        return subprocess.run(
            [sys.executable, str(SCRIPTS / name)],
            cwd=self.root, env=self.env, capture_output=True, text=True, timeout=15,
        )

    def check(self):
        return self.run_script("check_qa.py")

    def run_tests(self, source):
        (self.backend / "test_sample.py").write_text(source)
        return self.run_script("run_backend_tests.py")

    def test_registered_test_passes_when_it_runs_successfully(self):
        result = self.run_tests(
            "import unittest\nclass ExistingTests(unittest.TestCase):\n"
            "    def test_existing(self): pass\n"
            "    @unittest.skip('skipped')\n"
            "    def test_other(self): pass\n"
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        output = self.output.read_text()
        self.assertEqual(json.loads(output.split("=", 1)[1]), [EXISTING])
        self.env["PASSED_TESTS"] = output.split("=", 1)[1]
        self.register([EXISTING])
        result = self.check()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("1 required tests", result.stdout)
        self.register([EXISTING, OTHER])
        result = self.check()
        self.assertEqual(result.returncode, 1)
        self.assertIn(OTHER, result.stderr)

    def test_required_test_must_actually_run(self):
        self.register([EXISTING, OTHER])
        result = self.check()
        self.assertEqual(result.returncode, 1)
        self.assertIn(OTHER, result.stderr)

    def test_missing_registration_fails(self):
        result = self.check()
        self.assertEqual(result.returncode, 1)
        self.assertIn("Issue #7 is missing", result.stderr)

    def test_invalid_registration_fails(self):
        for ids in ([], [None], [""]):
            with self.subTest(ids=ids):
                self.register(ids)
                result = self.check()
                self.assertEqual(result.returncode, 1)
                self.assertIn("required", result.stderr)

    def test_missing_issue_reference_fails(self):
        self.pr.write_text(json.dumps({"body": "Compare with #7"}))
        result = self.check()
        self.assertEqual(result.returncode, 1)
        self.assertIn("Issue reference", result.stderr)

    def test_multiple_issues_reuse_the_same_result(self):
        self.pr.write_text(json.dumps({"number": 99, "body": "Refs #7, #8\nCloses #9（测试）"}))
        self.register([EXISTING])
        self.register([EXISTING, OTHER], issue=8)
        self.register([OTHER], issue=9)
        self.env["PASSED_TESTS"] = json.dumps([EXISTING, OTHER])
        result = self.check()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("2 required tests for Issues #7, #8, #9", result.stdout)

    def test_scrum_only_skips_registration(self):
        self.changed.write_bytes(b"docs/scrum/week7.md\0")
        result = self.check()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.changed.write_bytes(b"docs/scrum/week7.md\0backend/app/main.py\0")
        self.assertNotEqual(self.check().returncode, 0)

    def test_missing_results_fail_even_for_scrum(self):
        self.changed.write_bytes(b"docs/scrum/week7.md\0")
        self.env["PASSED_TESTS"] = ""
        result = self.check()
        self.assertEqual(result.returncode, 1)
        self.assertIn("Backend test results", result.stderr)

    def test_failure_outside_required_list_still_blocks(self):
        self.register([EXISTING])
        result = self.run_tests(
            "import unittest\nclass ExistingTests(unittest.TestCase):\n"
            "    def test_existing(self): pass\n"
            "    def test_other(self): self.fail('regression')\n"
        )
        self.assertEqual(result.returncode, 1)
        self.assertFalse(self.output.exists())
        self.env["BACKEND_RESULT"] = "failure"
        self.assertNotEqual(self.check().returncode, 0)

    def test_empty_or_interrupted_discovery_fails(self):
        for source in ("", "raise SystemExit(0)\n"):
            with self.subTest(source=source):
                self.assertEqual(self.run_tests(source).returncode, 1)
                self.assertFalse(self.output.exists())
