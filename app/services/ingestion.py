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

# Maximum characters per embedding request (Ollama has context limits)
CHUNK_SIZE = 2000


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

    # Chunk text and average embeddings
    chunks = _split_text(text_content, CHUNK_SIZE)
    embeddings = embedding_service.get_embeddings_batch(chunks)
    avg_embedding = _average_embeddings(embeddings)

    with Session(engine) as session:
        session.add(report)
        session.commit()
        session.refresh(report)

        embedding = Embedding(
            report_id=report.id,
            vector=avg_embedding,
            model_name=settings.embedding_model,
        )
        session.add(embedding)
        session.commit()

    archive_dir = pdf_path.parent / "archive"
    archive_dir.mkdir(exist_ok=True)
    move(str(pdf_path), archive_dir / pdf_path.name)

    return report


def _split_text(text: str, chunk_size: int) -> list[str]:
    """Split text into chunks of approximately chunk_size characters."""
    if len(text) <= chunk_size:
        return [text] if text.strip() else ["empty document"]

    chunks: list[str] = []
    for i in range(0, len(text), chunk_size):
        chunk = text[i : i + chunk_size].strip()
        if chunk:
            chunks.append(chunk)

    return chunks if chunks else ["empty document"]


def _average_embeddings(embeddings: list[list[float]]) -> list[float]:
    """Average multiple embedding vectors into one."""
    if not embeddings:
        return []
    if len(embeddings) == 1:
        return embeddings[0]

    dim = len(embeddings[0])
    avg = [0.0] * dim
    for emb in embeddings:
        for i in range(dim):
            avg[i] += emb[i]
    return [v / len(embeddings) for v in avg]
