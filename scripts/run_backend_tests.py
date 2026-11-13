"""Run the backend suite and publish the IDs of tests that passed."""

import json
import os
from pathlib import Path
import unittest


class TestResult(unittest.TextTestResult):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.passed = set()

    def addSuccess(self, test):
        super().addSuccess(test)
        self.passed.add(test.id())


def main():
    try:
        suite = unittest.defaultTestLoader.discover("backend/tests", pattern="test_*.py")
        result = unittest.TextTestRunner(verbosity=2, resultclass=TestResult).run(suite)
    except SystemExit as error:
        raise SystemExit("Backend test run exited before completion") from error
    if not result.wasSuccessful():
        return 1
    if not result.passed:
        raise SystemExit("No backend tests passed")
    if output := os.environ.get("GITHUB_OUTPUT"):
        with Path(output).open("a", encoding="utf-8") as stream:
            print(f"passed_tests={json.dumps(sorted(result.passed))}", file=stream)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
