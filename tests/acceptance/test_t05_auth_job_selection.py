"""Reuse the real auth/catalog integration suite for T05 acceptance."""

from pathlib import Path
import unittest


def load_tests(loader, tests, pattern):
    backend_tests = Path(__file__).resolve().parents[2] / "backend" / "tests"
    return unittest.TestLoader().discover(
        str(backend_tests), pattern="test_auth_catalog.py",
        top_level_dir=str(backend_tests),
    )
