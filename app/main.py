"""
INPUT:
- FastAPI application startup context.
OUTPUT:
- Configured FastAPI instance with routers and health endpoints.
"""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine

from app.api import forge, hawk, scry
from app.config import settings
from app.models.report import Base

app = FastAPI(title="Nexus Backend", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(scry.router)
app.include_router(forge.router)
app.include_router(hawk.router)


@app.on_event("startup")
async def startup_event() -> None:
    db_path = settings.db_path
    db_path.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
