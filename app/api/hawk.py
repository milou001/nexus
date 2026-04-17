"""
INPUT:
- FastAPI application instance wiring in Hawk-related routes.
OUTPUT:
- API router placeholder for reference cross-check endpoints.
"""
from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(prefix="/api/hawk", tags=["hawk"])


@router.get("/health")
def hawk_health() -> dict[str, str]:
    return {"status": "hawk-ok"}
