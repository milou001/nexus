"""
INPUT:
- Search parameters including query text, limits, report types, and optional year filter.
OUTPUT:
- Ranked list of search results with metadata and relevance scores.
"""
from __future__ import annotations

from math import sqrt

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.models.report import Embedding, Report
from app.schemas.scry import SearchResult
from app.services.embedder import embedding_service


def _cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
    dot = sum(a * b for a, b in zip(vec_a, vec_b))
    norm_a = sqrt(sum(a * a for a in vec_a))
    norm_b = sqrt(sum(b * b for b in vec_b))
    return dot / (norm_a * norm_b + 1e-8)


def search(query: str, limit: int, report_types: list[str], year: str | None) -> list[SearchResult]:
    engine = create_engine(f"sqlite:///{settings.db_path}")

    # Early return if no reports exist (skip embedding call)
    with Session(engine) as session:
        report_count = session.scalar(select(func.count()).select_from(Report))
        if report_count == 0:
            return []

    query_embedding = embedding_service.get_embedding(query)

    stmt = select(Report).join(Embedding, Report.id == Embedding.report_id)
    if report_types:
        stmt = stmt.filter(Report.type.in_(report_types))
    if year:
        stmt = stmt.filter(Report.year == year)

    results: list[SearchResult] = []
    with Session(engine) as session:
        rows = session.execute(stmt).all()
        if not rows:
            return []
        for (report,) in rows:
            emb = session.query(Embedding).filter(Embedding.report_id == report.id).first()
            if not emb or not isinstance(emb.vector, list) or not emb.vector:
                continue
            relevance = _cosine_similarity(query_embedding, emb.vector)
            results.append(
                SearchResult(
                    id=report.id,
                    report_number=report.report_number,
                    title=report.title,
                    year=report.year,
                    type=report.type,
                    relevance=relevance,
                    pdf_url=report.file_path,
                    hits=[],
                )
            )

    results.sort(key=lambda item: item.relevance, reverse=True)
    return results[:limit]
