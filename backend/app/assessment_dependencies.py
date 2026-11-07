"""Assessment adapters for the shared database, sessions, roles and T07 scorer."""

import hashlib
import secrets
import time

from fastapi import Depends, HTTPException, Request

from .catalog import ROLE_MAP
from .db import connect


def get_db(request: Request):
    con = connect(request.app.state.settings)
    try:
        yield con
    finally:
        con.close()


def require_assessment_user(request: Request, con=Depends(get_db)) -> str:
    """Read existing server sessions; never take an owner ID from the client.

    T04 can replace this dependency with its shared session guard when delivered.
    This adapter does not issue sessions or implement login/password handling.
    """
    settings = request.app.state.settings
    cookie = request.cookies.get(settings.cookie_name, "")
    if not cookie or len(cookie) > 200:
        raise HTTPException(401, "请先登录")
    row = con.execute(
        "SELECT s.user_id,s.csrf_token,s.expires_at FROM sessions s "
        "JOIN users u ON u.id=s.user_id WHERE s.token_hash=?",
        (hashlib.sha256(cookie.encode("utf-8")).hexdigest(),),
    ).fetchone()
    if row is None or row["expires_at"] <= time.time():
        raise HTTPException(401, "登录状态已过期，请重新登录")
    if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
        expected_origin = settings.origin or str(request.base_url).rstrip("/")
        origin = request.headers.get("origin")
        if request.headers.get("sec-fetch-site") == "cross-site" or (
            origin and origin.rstrip("/") != expected_origin.rstrip("/")
        ):
            raise HTTPException(403, "请求来源不受信任")
        token = request.headers.get("x-csrf-token", "")
        if not token or not token.isascii() or len(token) > 200 or not secrets.compare_digest(row["csrf_token"], token):
            raise HTTPException(403, "请求校验失败，请刷新后重试")
    return row["user_id"]


def get_assessment_roles() -> dict:
    # Alpha API currently proposes backend only. Explicit T04 enabled flags win.
    return {
        key: role for key, role in ROLE_MAP.items()
        if role.get("enabled", key == "backend")
    }


def score_snapshot(attempt: dict, submitted_at: str) -> dict:
    """Import on use so draft operations work before T07 is installed."""
    try:
        from .scoring import ScoringError, build_report
    except ModuleNotFoundError as exc:
        if exc.name != f"{__package__}.scoring":
            raise
        raise HTTPException(503, "评分模块尚未就绪，已保存的答案不受影响") from exc
    try:
        return build_report(attempt, submitted_at)
    except ScoringError as exc:
        raise HTTPException(422, "测评快照或答案无效，已保存的答案不受影响") from exc


def get_report_builder():
    return score_snapshot
