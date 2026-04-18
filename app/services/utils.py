"""
INPUT:
- No direct input; provides helper utilities shared across services.
OUTPUT:
- Utility functions for filename sanitization and report numbering.
"""
from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.report import Report

FILENAME_SAFE_PATTERN = re.compile(r"[^A-Za-z0-9_-]+")


def sanitize_filename(value: str, max_length: int = 50) -> str:
    normalized = FILENAME_SAFE_PATTERN.sub("_", value.strip())
    collapsed = re.sub(r"_+", "_", normalized)
    return collapsed.strip("_")[:max_length] or "untitled"


def format_report_filename(report_id: str, key: str, title: str, date_str: str, suffix: str) -> str:
    title_clean = sanitize_filename(title)
    key_clean = sanitize_filename(key)
    return f"{report_id}_{key_clean}_{title_clean}_{date_str}{suffix}"


def derive_document_date(pdf_path: Path) -> str:
    try:
        stat = pdf_path.stat()
    except FileNotFoundError:
        return "undated"
    modified = datetime.fromtimestamp(stat.st_mtime)
    return modified.strftime("%Y-%m-%d")


def generate_report_number(session: Session) -> str:
    stmt = select(Report.report_number).order_by(Report.report_number.desc()).limit(1)
    last_number = session.scalar(stmt)
    if last_number and last_number.isdigit():
        next_value = int(last_number) + 1
    else:
        next_value = 1
    return f"{next_value:07d}"
