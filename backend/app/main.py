import os
from fastapi import FastAPI
from .reports import router as reports_router

app=FastAPI(
    title=os.getenv("APP_NAME","SkillProof"),
    version="0.1.0-alpha",
    )

app.include_router(reports_router)

@app.get("/api/health")
def health() -> dict[str,str]:
    return{"Status":"ok"}
