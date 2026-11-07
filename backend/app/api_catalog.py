"""Public T04 catalog projected from T03 content; never includes question data."""
from fastapi import APIRouter, Request

from .catalog import DIMENSION_IDS, ROLES
from .db import load_content

router = APIRouter(prefix="/api", tags=["catalog"])


def load_catalog(content_dir):
    tree = load_content(content_dir, "ability-tree.json")
    role = tree["role"]
    dimensions = tree["dimensions"]
    if role["id"] != "backend" or len(dimensions) != 6 or {d["id"] for d in dimensions} != set(DIMENSION_IDS):
        raise ValueError("T03 ability tree must define backend and exactly the six contract dimensions")
    topics = {}
    topic_ids = set()
    public_dimensions = []
    for dimension in dimensions:
        public_dimensions.append({key: dimension[key] for key in ("id", "name", "description")})
        entries = dimension["topics"]
        if not entries:
            raise ValueError("Each dimension must have knowledge points")
        for entry in entries:
            if not entry["id"].startswith(dimension["id"] + ".") or entry["id"] in topic_ids or not entry["name"].strip():
                raise ValueError("Invalid or duplicate T03 topic")
            topic_ids.add(entry["id"])
        topics[dimension["id"]] = [entry["name"] for entry in entries]
    roles = []
    for existing in ROLES:
        enabled = existing["id"] == "backend"
        source = role if enabled else existing
        roles.append({
            **{key: source[key] for key in ("id", "name", "description")},
            "enabled": enabled,
            # Other roles have no T03 ability tree yet.
            "topics": topics if enabled else {},
        })
    return {"roles": roles, "dimensions": public_dimensions}


@router.get("/catalog")
def catalog(request: Request):
    return request.app.state.catalog
