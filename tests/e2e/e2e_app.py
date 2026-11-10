"""Run the real API with the isolated browser-test question bank."""

from dataclasses import replace
from pathlib import Path
from app.config import Settings
from app.main import create_app

app = create_app(replace(Settings(), content_dir=Path(__file__).parent / 'fixtures'))
