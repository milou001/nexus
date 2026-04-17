"""
INPUT:
- FastAPI application instance wiring in Forge-related routes.
OUTPUT:
- API router placeholder for document generation endpoints.
"""
from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(prefix="/api/forge", tags=["forge"])


@router.get("/health")
def forge_health() -> dict[str, str]:
    return {"status": "forge-ok"}
