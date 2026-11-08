"""Exercise the QA command in small, isolated sample repositories."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest


SOURCE = Path(__file__).resolve().parents[2] / "scripts" / "check_qa.py"
EXISTING_TEST = "test_sample.ExistingTests.test_existing"


class QACheckTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.tests = self.root / "tests" / "acceptance"
        self.requests = self.tests / "requests"
        self.requests.mkdir(parents=True)
        self.script = self.root / "scripts" / "check_qa.py"
        self.script.parent.mkdir()
        shutil.copyfile(SOURCE, self.script)
        self.write_tests("""
            import unittest
            class ExistingTests(unittest.TestCase):
                def test_existing(self):
                    self.assertEqual(2 + 3, 5)
        """)

    def write_tests(self, content):
        (self.tests / "test_sample.py").write_text(
            textwrap.dedent(content), encoding="utf-8"
        )

    def register(self, tests, pr=7):
        (self.requests / f"{pr}.json").write_text(
            json.dumps({"required_tests": tests}), encoding="utf-8"
        )

    def run_check(self, pr=7):
        return subprocess.run(
            [sys.executable, str(self.script), "--pr", str(pr)],
            cwd=self.root,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
            capture_output=True,
            text=True,
            timeout=15,
        )

    def test_missing_registration_fails(self):
        self.register([EXISTING_TEST], pr=6)
        result = self.run_check()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("7.json", result.stderr)
        self.assertIn("test_existing", result.stderr)

    def test_required_test_must_actually_run(self):
        self.register(["test_sample.ExistingTests.test_new_feature"])
        result = self.run_check()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("test_sample.ExistingTests.test_new_feature", result.stderr)

    def test_registered_test_passes_when_it_runs_successfully(self):
        self.register(["test_sample.ObsoleteTests.test_removed"], pr=6)
        self.register([EXISTING_TEST])
        result = self.run_check()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("test_existing", result.stderr)

    def test_failure_outside_required_list_still_blocks(self):
        self.write_tests("""
            import unittest
            class ExistingTests(unittest.TestCase):
                def test_existing(self):
                    self.assertEqual(2 + 3, 5)
                def test_regression(self):
                    self.fail("An existing feature is broken")
        """)
        self.register([EXISTING_TEST])
        result = self.run_check()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("test_existing", result.stderr)
        self.assertIn("An existing feature is broken", result.stderr)

    def test_invalid_registration_fails(self):
        contents = [
            "{", "null", "[]", "{}", '{"required_tests": []}',
            '{"required_tests": "test_sample.ExistingTests.test_existing"}',
            '{"required_tests": [null]}', '{"required_tests": [""]}',
        ]
        for content in contents:
            with self.subTest(content=content):
                (self.requests / "7.json").write_text(content, encoding="utf-8")
                result = self.run_check()
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("QA check failed", result.stderr)

    def test_required_failure_skip_or_expected_failure_blocks(self):
        methods = {
            "failure": 'def test_existing(self):\n    self.fail("broken")',
            "skip": 'def test_existing(self):\n    self.skipTest("not ready")',
            "expected_failure": (
                '@unittest.expectedFailure\n'
                'def test_existing(self):\n    self.fail("known failure")'
            ),
            "skipped_subtest": (
                'def test_existing(self):\n'
                '    with self.subTest(case="missing"):\n'
                '        self.skipTest("not ready")'
            ),
        }
        self.register([EXISTING_TEST])
        for status, method in methods.items():
            with self.subTest(status=status):
                self.write_tests(
                    "import unittest\nclass ExistingTests(unittest.TestCase):\n"
                    + textwrap.indent(method, "    ") + "\n"
                )
                result = self.run_check()
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("Required tests did not pass", result.stderr)
                self.assertIn(EXISTING_TEST, result.stderr)

    def test_empty_or_interrupted_discovery_fails(self):
        self.register([EXISTING_TEST])
        for content in ["", "import nonexistent_qa_fixture_module", "raise SystemExit(0)"]:
            with self.subTest(content=content):
                self.write_tests(content)
                result = self.run_check()
                self.assertNotEqual(result.returncode, 0)

    def test_exit_during_setup_or_cleanup_fails(self):
        self.register(["test_sample.ExistingTests.test_not_written"])
        for hook in ["setUpModule", "tearDownModule", "setUpClass", "tearDownClass"]:
            with self.subTest(hook=hook):
                source = (
                    "import unittest\nclass ExistingTests(unittest.TestCase):\n"
                    "    def test_existing(self):\n        self.assertTrue(True)\n"
                )
                if hook.endswith("Class"):
                    source += (
                        f"    @classmethod\n    def {hook}(cls):\n"
                        "        raise SystemExit(0)\n"
                    )
                else:
                    source += f"def {hook}():\n    raise SystemExit(0)\n"
                self.write_tests(source)
                result = self.run_check()
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("exited before completion", result.stderr)

    def test_invalid_pr_number_fails(self):
        self.register([EXISTING_TEST])
        for pr in [0, -1, "../7"]:
            with self.subTest(pr=pr):
                result = self.run_check(pr)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("--pr", result.stderr)


if __name__ == "__main__":
    unittest.main()
