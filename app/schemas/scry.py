"""
INPUT:
- Raw payloads for Scry search operations.
OUTPUT:
- Validated Pydantic schemas for requests and responses.
"""
from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class SearchRequest(BaseModel):
    """Schema for semantic search requests."""

    query: str = Field(..., min_length=1)
    limit: int = Field(10, ge=1, le=100)
    report_types: List[str] = Field(default_factory=list)
    year: Optional[str] = Field(default=None)


class SearchResult(BaseModel):
    """Schema representing a single search result."""

    id: int
    report_number: str
    title: str
    year: str
    type: str
    relevance: float
    pdf_url: str
    hits: List[str]
