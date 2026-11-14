"""Public T04 catalog projected from T03 content; never includes question data."""
from fastapi import APIRouter, Request

from .catalog import project_catalog
from .db import load_content

router = APIRouter(prefix="/api", tags=["catalog"])


def load_catalog(content_dir):
    tree = load_content(content_dir, "ability-tree.json")
    return project_catalog(tree)


@router.get("/catalog")
def catalog(request: Request):
    return request.app.state.catalog
