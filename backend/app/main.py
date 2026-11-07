import os
from contextlib import asynccontextmanager

from fastapi import FastAPI

from .config import Settings
from .db import initialize
from .api_assessments import router as assessments_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = Settings()
    initialize(settings)
    app.state.settings = settings
    yield


app = FastAPI(
    title=os.getenv("APP_NAME", "SkillProof"),
    version="0.1.0-alpha",
    lifespan=lifespan,
)
app.include_router(assessments_router)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"Status": "ok"}
