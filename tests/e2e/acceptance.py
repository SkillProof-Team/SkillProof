"""Expose browser suites to the existing unittest and PR registration runner."""

import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


DIRECTORY = Path(__file__).resolve().parent


class BrowserAcceptanceTests(unittest.TestCase):
    pass


def browser_test(script):
    def run(self):
        parent = Path(os.environ.get('SKILLPROOF_E2E_OUTPUT', tempfile.gettempdir()))
        parent.mkdir(parents=True, exist_ok=True)
        output = tempfile.mkdtemp(prefix=script.stem + '-', dir=parent)
        result = subprocess.run([
            sys.executable, str(DIRECTORY / 'run.py'),
            '--suite', script.stem, '--output', output,
        ])
        self.assertEqual(result.returncode, 0, f'Browser suite failed; results: {output}')
    return run


scripts = sorted(DIRECTORY.glob('test_*.cjs'))
if not scripts:
    raise RuntimeError('Browser test registration has no test suites')
for script in scripts:
    setattr(BrowserAcceptanceTests, script.stem, browser_test(script))
