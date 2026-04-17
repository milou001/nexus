"""
INPUT:
- FastAPI application instance wiring in Scry-specific routes.
OUTPUT:
- API router handling search and report retrieval endpoints.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.config import settings
from app.models.report import Report
from app.schemas.scry import SearchRequest, SearchResult
from app.services.searcher import search

router = APIRouter(prefix="/api/scry", tags=["scry"])


@router.post("/search", response_model=list[SearchResult])
def search_reports(payload: SearchRequest) -> list[SearchResult]:
    return search(payload.query, payload.limit, payload.report_types, payload.year)


@router.get("/reports/{report_id}", response_model=SearchResult)
def get_report(report_id: int) -> SearchResult:
    engine = create_engine(f"sqlite:///{settings.db_path}")
    with Session(engine) as session:
        report = session.get(Report, report_id)
        if report is None:
            raise HTTPException(status_code=404, detail="Report not found")
        return SearchResult(
            id=report.id,
            report_number=report.report_number,
            title=report.title,
            year=report.year,
            type=report.type,
            relevance=1.0,
            pdf_url=report.file_path,
            hits=[],
        )


@router.get("/health")
def scry_health() -> dict[str, str]:
    return {"status": "ok"}
