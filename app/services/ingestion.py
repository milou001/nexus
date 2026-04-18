"""
INPUT:
- file_path: str — Path to the PDF file that should be ingested.
OUTPUT:
- Persisted Report ORM instance with associated chapters and embeddings.
"""
from __future__ import annotations

from pathlib import Path
from shutil import move

import fitz  # type: ignore
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.config import settings
from app.models.report import Base, Chapter, Embedding, Report
from app.services.chapterizer import Chapterizer
from app.services.chapterizer import ChapterizerResult
from app.services.embedder import embedding_service
from app.services.pdf_splitter import split_pdf
from app.services.utils import (
    derive_document_date,
    format_report_filename,
    generate_report_number,
)

CHUNK_SIZE = 2000


def ingest_pdf(file_path: str) -> Report:
    """Ingest a PDF, persist report data, split chapters, and create embeddings."""
    engine = create_engine(f"sqlite:///{settings.db_path}")
    Base.metadata.create_all(engine)

    pdf_path = Path(file_path)
    if not pdf_path.exists():
        raise FileNotFoundError(file_path)

    chapterizer = Chapterizer()
    detection = chapterizer.detect_chapters(str(pdf_path))

    with Session(engine) as session:
        report_number = generate_report_number(session)
        document_date = derive_document_date(pdf_path)
        originals_dir = settings.originals_path
        originals_dir.mkdir(parents=True, exist_ok=True)
        report_filename = format_report_filename(report_number, "Orig", pdf_path.stem, document_date, ".pdf")
        destination_original = originals_dir / report_filename
        move(str(pdf_path), destination_original)

        report = Report(
            report_number=report_number,
            title=pdf_path.stem,
            year=document_date[:4] if document_date != "undated" else "0000",
            type="internal",
            file_path=str(destination_original),
            content_text=detection.raw_text,
        )
        session.add(report)
        session.flush()

        _persist_chapters(
            session=session,
            report=report,
            report_number=report_number,
            document_date=document_date,
            original_pdf=destination_original,
            detection=detection,
        )

        session.commit()
        session.refresh(report)

    return report


def _persist_chapters(
    session: Session,
    report: Report,
    report_number: str,
    document_date: str,
    original_pdf: Path,
    detection: ChapterizerResult,
) -> None:
    for chapter_info in detection.chapters:
        chapter_pdf_name = format_report_filename(
            report_number,
            chapter_info.key,
            chapter_info.title,
            document_date,
            ".pdf",
        )
        chapter_directory = settings.chapters_path / chapter_info.key
        chapter_directory.mkdir(parents=True, exist_ok=True)
        chapter_pdf_path = chapter_directory / chapter_pdf_name
        split_pdf(str(original_pdf), chapter_info.page_start, chapter_info.page_end, str(chapter_pdf_path))

        chapter_text = _extract_text(chapter_pdf_path)
        chapter = Chapter(
            report_id=report.id,
            chapter_key=chapter_info.key,
            chapter_title=chapter_info.title,
            chapter_subtitle=chapter_info.subtitle,
            page_start=chapter_info.page_start,
            page_end=chapter_info.page_end,
            file_path=str(chapter_pdf_path),
            content_text=chapter_text,
        )
        session.add(chapter)
        session.flush()

        chunks = _split_text(chapter_text, CHUNK_SIZE)
        vectors = embedding_service.get_embeddings_batch(chunks)
        embedding = Embedding(
            chapter_id=chapter.id,
            vector=_average_embeddings(vectors),
            model_name=settings.embedding_model,
        )
        session.add(embedding)


def _extract_text(pdf_path: Path) -> str:
    with fitz.open(pdf_path) as doc:
        return "\n".join(page.get_text() for page in doc)


def _split_text(text: str, chunk_size: int) -> list[str]:
    if len(text) <= chunk_size:
        return [text] if text.strip() else ["empty document"]

    chunks: list[str] = []
    for i in range(0, len(text), chunk_size):
        chunk = text[i : i + chunk_size].strip()
        if chunk:
            chunks.append(chunk)

    return chunks if chunks else ["empty document"]


def _average_embeddings(embeddings: list[list[float]]) -> list[float]:
    if not embeddings:
        return []
    if len(embeddings) == 1:
        return embeddings[0]

    dim = len(embeddings[0])
    avg = [0.0] * dim
    for emb in embeddings:
        for idx in range(dim):
            avg[idx] += emb[idx]
    return [value / len(embeddings) for value in avg]
