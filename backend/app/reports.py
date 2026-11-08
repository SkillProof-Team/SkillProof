"""Read persisted reports without recomputing against the current question bank."""

import json
import sqlite3

from fastapi import APIRouter, Depends, HTTPException

from .security import Principal, get_db, require_user

router = APIRouter(prefix="/api", tags=["reports"])


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
    principal: Principal = Depends(require_user),
    connection=Depends(get_db),
) -> dict:
    return read_report(connection, attempt_id, principal.user["id"])
