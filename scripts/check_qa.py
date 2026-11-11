"""Check an Issue's required tests against the results of this CI run."""

import json
import os
from pathlib import Path
import re
import sys


ISSUE_REFERENCE = re.compile(
    r"(?:refs|closes|fixes|resolves)[ \t]+(#[1-9][0-9]*(?:\s*[,，]\s*#[1-9][0-9]*)*)"
    r"(?:[ \t]*[（(].*[）)])?",
    re.IGNORECASE,
)


def issue_numbers(body):
    numbers = set()
    for line in body.splitlines():
        if match := ISSUE_REFERENCE.fullmatch(line.strip()):
            numbers.update(re.findall(r"#([0-9]+)", match[1]))
    return numbers


def test_ids(values, source):
    if not isinstance(values, list) or not values or any(
        not isinstance(value, str) or not value.strip() for value in values
    ):
        raise ValueError(f"{source} must contain a non-empty list of test IDs")
    return set(values)


def main():
    if os.environ.get("FRONTEND_RESULT") != "success" or os.environ.get("BACKEND_RESULT") != "success":
        raise ValueError("Frontend and backend checks must both pass")

    passed = test_ids(json.loads(os.environ.get("PASSED_TESTS") or "null"), "Backend test results")
    changed = Path(os.environ["CHANGED_FILES"]).read_bytes().split(b"\0")
    paths = [path for path in changed if path]
    if paths and all(path.startswith(b"docs/scrum/") and path.endswith(b".md") for path in paths):
        print("Only Scrum Markdown changed. Required test registration is not needed.")
        return 0

    pr = json.loads(Path(os.environ["PR_DETAILS"]).read_text(encoding="utf-8"))
    issues = issue_numbers(pr.get("body") or "")
    if not issues:
        raise ValueError("Add an Issue reference on its own line in the PR body, e.g. Refs #40")

    required = set()
    for issue in sorted(issues, key=int):
        registration = Path("tests/acceptance/issues") / f"{issue}.json"
        try:
            data = json.loads(registration.read_text(encoding="utf-8"))
        except FileNotFoundError:
            raise ValueError(f"Issue #{issue} is missing its required test list: {registration}") from None
        ids = data.get("required_tests") if isinstance(data, dict) else None
        required.update(test_ids(ids, f"{registration}: required_tests"))

    missing = required - passed
    if missing:
        raise ValueError("Required tests did not pass: " + ", ".join(sorted(missing)))
    print(f"QA checks passed: {len(required)} required tests for Issues " + ", ".join(
        f"#{issue}" for issue in sorted(issues, key=int)
    ))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, KeyError) as error:
        sys.exit(f"QA check failed: {error}")
