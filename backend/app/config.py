"""Explicit, environment-driven single-node deployment settings."""

from dataclasses import dataclass, field
from pathlib import Path
import os
from .url_validation import https_url

APP_DIR = Path(__file__).resolve().parent


@dataclass(frozen=True)
class Settings:
    database_path: Path = field(default_factory=lambda: Path(os.getenv("SKILLPROOF_DB_PATH", str(APP_DIR.parent / "data" / "skillproof.db"))))
    content_dir: Path = APP_DIR / "content"
    frontend_dir: Path = APP_DIR.parent.parent / "frontend" / "dist"
    environment: str = field(default_factory=lambda: os.getenv("SKILLPROOF_ENV", "development"))
    cookie_secure: bool = field(default_factory=lambda: os.getenv("SKILLPROOF_COOKIE_SECURE", "0") == "1")
    allowed_hosts: tuple[str, ...] = field(
        default_factory=lambda: tuple(x.strip() for x in os.getenv("SKILLPROOF_ALLOWED_HOSTS", "localhost,127.0.0.1,testserver").split(",") if x.strip())
    )
    origin: str | None = field(default_factory=lambda: os.getenv("SKILLPROOF_ORIGIN") or None)
    session_seconds: int = 24 * 60 * 60
    max_body_bytes: int = 131072
    login_limit: int = 20
    register_limit: int = 10
    rate_window_seconds: int = 900

    @property
    def cookie_name(self) -> str:
        return "__Host-skillproof_session" if self.cookie_secure else "skillproof_session"

    def validate(self) -> None:
        if self.environment == "production":
            if not self.cookie_secure:
                raise ValueError("Production requires SKILLPROOF_COOKIE_SECURE=1 and HTTPS termination.")
            try:
                parsed = https_url(self.origin or "")
            except ValueError as exc:
                raise ValueError("Production requires a valid HTTPS SKILLPROOF_ORIGIN.") from exc
            if (
                parsed.scheme != "https"
                or not parsed.hostname
                or parsed.username
                or parsed.password
                or parsed.path not in ("", "/")
                or parsed.query
                or parsed.fragment
            ):
                raise ValueError("Production requires an HTTPS SKILLPROOF_ORIGIN.")
            if "*" in self.allowed_hosts:
                raise ValueError("Production requires explicit SKILLPROOF_ALLOWED_HOSTS.")
            if parsed.hostname not in self.allowed_hosts:
                raise ValueError("SKILLPROOF_ORIGIN hostname must be in SKILLPROOF_ALLOWED_HOSTS.")
