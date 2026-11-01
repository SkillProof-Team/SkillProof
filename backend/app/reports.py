"""Read persisted reports without recomputing against the current question bank."""

import json
import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Request

router = APIRouter(prefix="/api", tags=["reports"])


def require_report_user() -> str:
    """T03 must override this dependency with a verified session user ID.

    Fail closed until authentication is integrated. Never read an identity from
    a query parameter, body, or unverified header.
    """
    raise HTTPException(401, "请先登录")


def get_report_connection(request: Request):
    """T02 supplies app.state.report_connection_factory, one SQLite connection/request.

    The factory owns database configuration. This module never creates tables,
    seeds data, or guesses a database path. Connections are closed after use.
    """
    factory = getattr(request.app.state, "report_connection_factory", None)
    if factory is None:
        raise HTTPException(503, "结果存储尚未接入")
    connection = factory()
    try:
        yield connection
    finally:
        connection.close()


def read_report(connection: sqlite3.Connection, attempt_id: str, user_id: str) -> dict:
    row = connection.execute(
        "SELECT status, report_json FROM attempts WHERE id=? AND user_id=?",
        (attempt_id, user_id),
    ).fetchone()
    if row is None:
        raise HTTPException(404, "测评不存在")
    if row[0] != "submitted":
        raise HTTPException(409, "测评提交后才会生成报告")
    try:
        report = json.loads(row[1])
        if not isinstance(report, dict) or report.get("id") != attempt_id:
            raise ValueError("Invalid report snapshot")
    except (ValueError, TypeError) as exc:
        raise HTTPException(500, "结果快照无效") from exc
    return report


@router.get("/reports/{attempt_id}")
def get_report(
    attempt_id: str,
    user_id: str = Depends(require_report_user),
    connection=Depends(get_report_connection),
) -> dict:
    return read_report(connection, attempt_id, user_id)
