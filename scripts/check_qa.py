"""Run acceptance tests and check the current PR's required tests."""

import argparse
import json
from pathlib import Path
import sys
import unittest


class QAResult(unittest.TextTestResult):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.passed = set()

    def addSuccess(self, test):
        super().addSuccess(test)
        self.passed.add(test.id())


def read_required_tests(path):
    data = json.loads(path.read_text(encoding="utf-8"))
    required = data.get("required_tests") if isinstance(data, dict) else None
    if not isinstance(required, list) or not required or any(
        not isinstance(name, str) or not name.strip() for name in required
    ):
        raise ValueError(f"{path}: required_tests must be a non-empty list of test IDs")
    return set(required)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pr", type=int, required=True)
    args = parser.parse_args()
    if args.pr <= 0:
        parser.error("--pr must be a positive PR number")

    root = Path(__file__).resolve().parents[1]
    registration = root / "tests" / "acceptance" / "requests" / f"{args.pr}.json"
    try:
        suite = unittest.defaultTestLoader.discover(
            str(root / "tests" / "acceptance"), pattern="test_*.py"
        )
    except (ImportError, SystemExit) as error:
        print(f"QA test discovery failed: {error}", file=sys.stderr)
        return 1
    if suite.countTestCases() == 0:
        print("No acceptance tests were discovered", file=sys.stderr)
        return 1

    try:
        result = unittest.TextTestRunner(verbosity=2, resultclass=QAResult).run(suite)
    except SystemExit as error:
        print(f"Acceptance tests exited before completion: {error}", file=sys.stderr)
        return 1
    try:
        required = read_required_tests(registration)
    except (OSError, UnicodeError, ValueError) as error:
        print(f"QA check failed: {error}", file=sys.stderr)
        return 1
    missing = required - result.passed
    if missing:
        print(
            "Required tests did not pass: " + ", ".join(sorted(missing)),
            file=sys.stderr,
        )
    if missing or not result.wasSuccessful():
        return 1
    print(f"QA checks passed for PR {args.pr}: {len(required)} required tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
