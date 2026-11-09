"""Opaque sessions, CSRF validation, password hashing and bounded login attempts."""

from dataclasses import dataclass
import hashlib
import secrets
import sqlite3
import time
from urllib.parse import urlsplit

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from fastapi import Depends, HTTPException, Request, Response

from .config import Settings
from .db import connect, now_iso, transaction

PASSWORD_HASHER = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=1, hash_len=32, salt_len=16)
_DUMMY_HASH = PASSWORD_HASHER.hash(secrets.token_urlsafe(32))
UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


def password_matches(hashed: str, password: str) -> bool:
    try:
        return PASSWORD_HASHER.verify(hashed, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def dummy_verify(password: str) -> None:
    password_matches(_DUMMY_HASH, password)


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def get_db(request: Request):
    con = connect(request.app.state.settings)
    try:
        yield con
    finally:
        con.close()


def public_user(row) -> dict:
    return {"id": row["id"], "email": row["email"], "name": row["name"], "role": row["role"], "targetRole": row["target_role"], "createdAt": row["created_at"]}


@dataclass
class Principal:
    user: sqlite3.Row
    session_hash: str
    csrf_token: str


def require_user(request: Request, con=Depends(get_db)) -> Principal:
    settings = request.app.state.settings
    cookie = request.cookies.get(settings.cookie_name, "")
    if not cookie or len(cookie) > 200:
        raise HTTPException(401, "请先登录")
    hashed = token_hash(cookie)
    row = con.execute("SELECT u.*,s.csrf_token,s.expires_at FROM users u JOIN sessions s ON s.user_id=u.id WHERE s.token_hash=?", (hashed,)).fetchone()
    if not row or row["expires_at"] <= time.time():
        raise HTTPException(401, "登录状态已过期，请重新登录")
    if request.method in UNSAFE_METHODS:
        token = request.headers.get("x-csrf-token", "")
        if not token or not token.isascii() or len(token) > 200 or not secrets.compare_digest(row["csrf_token"], token):
            raise HTTPException(403, "请求校验失败，请刷新后重试")
    return Principal(row, hashed, row["csrf_token"])


def require_admin(principal: Principal = Depends(require_user)) -> Principal:
    if principal.user["role"] != "admin":
        raise HTTPException(403, "需要管理员权限")
    return principal


def issue_session(con, user_id: str, response: Response, settings: Settings) -> tuple[str, str]:
    token = secrets.token_urlsafe(32)
    csrf = secrets.token_urlsafe(32)
    hashed = token_hash(token)
    con.execute("DELETE FROM sessions WHERE expires_at <= ?", (time.time(),))
    con.execute(
        "INSERT INTO sessions(token_hash,user_id,csrf_token,created_at,expires_at) VALUES(?,?,?,?,?)",
        (hashed, user_id, csrf, now_iso(), time.time() + settings.session_seconds),
    )
    response.set_cookie(
        settings.cookie_name, token, httponly=True, secure=settings.cookie_secure, samesite="strict", max_age=settings.session_seconds, path="/"
    )
    return hashed, csrf


def clear_cookie(response: Response, settings: Settings) -> None:
    response.delete_cookie(settings.cookie_name, path="/", httponly=True, secure=settings.cookie_secure, samesite="strict")


def check_rate_limit(con, request: Request, scope: str, subject: str = "") -> None:
    settings = request.app.state.settings
    # Proxy forwarding headers are deliberately not trusted here.
    peer = request.client.host if request.client else "local"
    keys = [token_hash(f"{scope}:ip:{peer}")]
    if subject:
        keys.append(token_hash(f"{scope}:account:{subject}"))
    limit = settings.register_limit if scope == "register" else settings.login_limit
    now = time.time()
    rejected = False
    retry_after = settings.rate_window_seconds
    with transaction(con):
        con.execute("DELETE FROM rate_limits WHERE expires_at <= ?", (now,))
        rows = [(key, con.execute("SELECT count,expires_at FROM rate_limits WHERE key_hash=?", (key,)).fetchone()) for key in keys]
        blocked = [row for _, row in rows if row and row["count"] >= limit]
        if blocked:
            rejected = True
            retry_after = max(1, int(max(row["expires_at"] for row in blocked) - now))
        else:
            # A blocked IP cannot create unbounded account buckets by varying email.
            for key, row in rows:
                if row:
                    con.execute("UPDATE rate_limits SET count=count+1 WHERE key_hash=?", (key,))
                else:
                    con.execute("INSERT INTO rate_limits(key_hash,count,expires_at) VALUES(?,1,?)", (key, now + settings.rate_window_seconds))
    if rejected:
        raise HTTPException(429, "操作过于频繁，请稍后重试", headers={"Retry-After": str(retry_after)})


def validate_origin(request: Request) -> bool:
    """Origin + Fetch Metadata cover login CSRF; CSRF tokens cover authenticated writes."""
    if request.method not in UNSAFE_METHODS:
        return True
    if request.headers.get("sec-fetch-site") == "cross-site":
        return False
    origin = request.headers.get("origin")
    if not origin:
        # Non-browser clients can omit Origin, but still need a session-bound CSRF token.
        return True
    try:
        parsed = urlsplit(origin)
    except ValueError:
        return False
    if not parsed.hostname or parsed.path or parsed.query or parsed.fragment or parsed.username or parsed.password:
        return False
    expected = request.app.state.settings.origin or str(request.base_url).rstrip("/")
    return origin.rstrip("/") == expected.rstrip("/")
