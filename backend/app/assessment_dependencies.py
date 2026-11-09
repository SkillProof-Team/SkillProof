"""Use the shared authentication, catalog and scoring contracts for assessments."""

from fastapi import Depends, HTTPException, Request

from .catalog import ROLE_MAP
from .scoring import ScoringError, build_report
from .security import Principal, require_user


def require_assessment_user(principal: Principal = Depends(require_user)) -> str:
    return principal.user["id"]


def get_assessment_roles(request: Request) -> dict:
    return {
        role["id"]: {**ROLE_MAP[role["id"]], "name": role["name"]}
        for role in request.app.state.catalog["roles"]
        if role["enabled"]
    }


def score_snapshot(attempt: dict, submitted_at: str) -> dict:
    try:
        return build_report(attempt, submitted_at)
    except ScoringError as exc:
        raise HTTPException(422, "测评快照或答案无效，已保存的答案不受影响") from exc


def get_report_builder():
    return score_snapshot
