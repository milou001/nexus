"""
INPUT:
- pdf_path: str — Path to the source PDF document.
- page_start: int — First page (1-based) to include.
- page_end: int — Last page (inclusive, 1-based) to include.
OUTPUT:
- Path to the generated partial PDF containing the requested page range.
"""
from __future__ import annotations

from pathlib import Path

import fitz  # type: ignore


def split_pdf(pdf_path: str, page_start: int, page_end: int, output_path: str) -> str:
    if page_start < 1 or page_end < page_start:
        raise ValueError("Invalid page range specified")

    source = Path(pdf_path)
    if not source.exists():
        raise FileNotFoundError(str(source))

    with fitz.open(source) as doc:
        if page_end > doc.page_count:
            raise ValueError("page_end exceeds document length")
        new_doc = fitz.open()
        try:
            for page_index in range(page_start - 1, page_end):
                new_doc.insert_pdf(doc, from_page=page_index, to_page=page_index)
            output_file = Path(output_path)
            output_file.parent.mkdir(parents=True, exist_ok=True)
            new_doc.save(output_file)
        finally:
            new_doc.close()

    return str(output_file)
