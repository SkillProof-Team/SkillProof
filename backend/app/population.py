"""One latest valid submitted vector per user and role; public output is aggregate only."""
import json
import math

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator

from .catalog import DIMENSION_IDS, ROLE_MAP
from .db import dump, now_iso, transaction
from .security import get_db, require_admin, require_user

router = APIRouter(prefix="/api", tags=["population"])


class Baseline(BaseModel):
    model_config = ConfigDict(extra="forbid")
    preset: dict[str, float]
    weight: float = Field(ge=0, le=1000000, allow_inf_nan=False)

    @field_validator("preset")
    @classmethod
    def six_scores(cls, value):
        if set(value) != set(DIMENSION_IDS) or any(
            not math.isfinite(x) or not 0 <= x <= 100 for x in value.values()
        ):
            raise ValueError("需要六个固定维度的 0–100 分数")
        return value


def valid_vector(row):
    try:
        report = json.loads(row["report_json"])
        if report.get("id") != row["id"] or report.get("roleId") != row["role_id"]:
            return None
        dimensions = report["dimensions"]
        if len(dimensions) != 6:
            return None
        vector = {d["id"]: d["score"] for d in dimensions}
        if set(vector) != set(DIMENSION_IDS):
            return None
        if any(isinstance(x, bool) or not isinstance(x, (int, float)) or
               not math.isfinite(x) or not 0 <= x <= 100 for x in vector.values()):
            return None
        return vector
    except (ValueError, TypeError, KeyError, AttributeError):
        return None


def refresh_population(con, role_id):
    """Caller owns the write transaction. Rebuild also handles deleted/corrupt snapshots."""
    if role_id not in ROLE_MAP:
        raise HTTPException(404, "岗位不存在")
    config = con.execute("SELECT * FROM population_config WHERE role_id=?", (role_id,)).fetchone()
    preset = json.loads(config["preset_json"]) if config else dict.fromkeys(DIMENSION_IDS, 50)
    weight = config["weight"] if config else 0
    current = {}
    rows = con.execute(
        "SELECT id,user_id,role_id,report_json FROM attempts WHERE role_id=? "
        "AND status='submitted' ORDER BY submitted_at DESC,created_at DESC,id DESC", (role_id,),
    )
    for row in rows:
        if row["user_id"] not in current:
            vector = valid_vector(row)
            if vector is not None:
                current[row["user_id"]] = (row["id"], vector)
    con.execute("DELETE FROM population_vectors WHERE role_id=?", (role_id,))
    con.executemany("INSERT INTO population_vectors VALUES(?,?,?,?)", [
        (role_id, uid, aid, dump(v)) for uid, (aid, v) in current.items()
    ])
    n = len(current)
    mean = {d: (weight * preset[d] + sum(v[d] for _, v in current.values())) / (weight + n)
            if n else preset[d] for d in DIMENSION_IDS}
    updated = now_iso()
    con.execute("INSERT OR REPLACE INTO population_summary VALUES(?,?,?,?)",
                (role_id, n, dump(mean), updated))
    return {"roleId": role_id, "sampleCount": n, "vector": mean,
            "preset": preset, "weight": weight,
            "source": "preset" if not n else "weighted" if weight else "samples",
            "updatedAt": updated}


@router.get("/roles/{role_id}/population")
def get_population(role_id: str, principal=Depends(require_user), con=Depends(get_db)):
    with transaction(con):
        return refresh_population(con, role_id)


@router.put("/admin/roles/{role_id}/population")
def set_population(role_id: str, payload: Baseline,
                   principal=Depends(require_admin), con=Depends(get_db)):
    if role_id not in ROLE_MAP:
        raise HTTPException(404, "岗位不存在")
    with transaction(con):
        con.execute("INSERT OR REPLACE INTO population_config VALUES(?,?,?)",
                    (role_id, dump(payload.preset), payload.weight))
        return refresh_population(con, role_id)
