"""
INPUT:
- File path pointing to a PDF requiring ingestion into the Nexus database.
OUTPUT:
- Persisted Report ORM instance with associated embedding metadata.
"""
from __future__ import annotations

from pathlib import Path
from shutil import move

import fitz  # type: ignore
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.config import settings
from app.models.report import Base, Embedding, Report
from app.services.embedder import embedding_service


def ingest_pdf(file_path: str) -> Report:
    engine = create_engine(f"sqlite:///{settings.db_path}")
    Base.metadata.create_all(engine)

    pdf_path = Path(file_path)
    if not pdf_path.exists():
        raise FileNotFoundError(file_path)

    with fitz.open(pdf_path) as doc:
        text_content = "\n".join(page.get_text() for page in doc)

    report = Report(
        report_number=pdf_path.stem,
        title=pdf_path.stem,
        year="0000",
        type="internal",
        file_path=str(pdf_path),
        content_text=text_content,
    )

    embedding_vector = embedding_service.get_embedding(text_content)
    embedding = Embedding(vector=embedding_vector, model_name=settings.embedding_model, report=report)

    with Session(engine) as session:
        session.add(report)
        session.add(embedding)
        session.commit()
        session.refresh(report)

    archive_dir = pdf_path.with_name("archive")
    archive_dir.mkdir(exist_ok=True)
    move(str(pdf_path), archive_dir / pdf_path.name)

    return report
