"""
INPUT:
- SQLAlchemy Declarative Base for metadata binding.
OUTPUT:
- Report, Chapter, and Embedding ORM models mapped to SQLite tables.
"""
from __future__ import annotations

from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.types import JSON


class Base(DeclarativeBase):
    """Base class for SQLAlchemy models."""


class Report(Base):
    """ORM model describing a technical report record."""

    __tablename__ = "reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    report_number: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    year: Mapped[str] = mapped_column(String(4), nullable=False)
    type: Mapped[str] = mapped_column(String(32), nullable=False)
    file_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    content_text: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    chapters: Mapped[list["Chapter"]] = relationship(
        "Chapter",
        back_populates="report",
        cascade="all, delete-orphan",
    )


class Chapter(Base):
    """ORM model describing a single chapter extracted from a report."""

    __tablename__ = "chapters"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    report_id: Mapped[int] = mapped_column(Integer, ForeignKey("reports.id"), nullable=False, index=True)
    chapter_key: Mapped[str] = mapped_column(String(32), nullable=False)
    chapter_title: Mapped[str] = mapped_column(String(512), nullable=False)
    chapter_subtitle: Mapped[str | None] = mapped_column(String(512), nullable=True)
    page_start: Mapped[int] = mapped_column(Integer, nullable=False)
    page_end: Mapped[int] = mapped_column(Integer, nullable=False)
    file_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    content_text: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    report: Mapped[Report] = relationship("Report", back_populates="chapters")
    embedding: Mapped["Embedding | None"] = relationship(
        "Embedding",
        back_populates="chapter",
        uselist=False,
        cascade="all, delete-orphan",
    )


class Embedding(Base):
    """ORM model describing an embedding vector for a chapter."""

    __tablename__ = "embeddings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    chapter_id: Mapped[int] = mapped_column(Integer, ForeignKey("chapters.id"), nullable=False, index=True)
    vector: Mapped[list[float]] = mapped_column(JSON, nullable=False)
    model_name: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    chapter: Mapped[Chapter] = relationship("Chapter", back_populates="embedding")
