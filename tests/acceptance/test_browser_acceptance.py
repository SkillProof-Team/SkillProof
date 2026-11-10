"""Run browser suites through the shared acceptance-test registration."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from e2e.acceptance import BrowserAcceptanceTests
