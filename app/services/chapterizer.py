"""
INPUT:
- pdf_path: str — Path to the source PDF file.
- ollama_url: str — Base URL of the Ollama server.
- model: str — Ollama model used for chapter detection.
OUTPUT:
- List[ChapterInfo] containing detected chapter metadata with page ranges.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import fitz  # type: ignore
import httpx
from pydantic import BaseModel, ValidationError

from app.config import settings


SEMANTIC_KEYS = {
    "SCOPE",
    "MODEL",
    "RESULT",
    "SUMM",
    "APPEND",
    "TEST",
    "LOAD",
    "BASIS",
    "GEO",
}


class ChapterInfo(BaseModel):
    """Structured chapter metadata extracted from a report."""

    key: str
    title: str
    subtitle: str | None = None
    page_start: int
    page_end: int

    @classmethod
    def validate_key(cls, key: str) -> str:
        key_upper = key.upper()
        return key_upper if key_upper in SEMANTIC_KEYS else "SCOPE"

    def model_post_init(self, __context: Any) -> None:  # type: ignore[override]
        self.key = self.validate_key(self.key)


@dataclass(slots=True)
class ChapterizerResult:
    chapters: list[ChapterInfo]
    raw_text: str


class Chapterizer:
    """Detects logical chapters in a PDF by combining heuristics and LLM analysis."""

    def __init__(self, ollama_url: str | None = None, model: str | None = None) -> None:
        self.ollama_url = ollama_url or settings.ollama_url
        self.model = model or settings.chapter_model
        self._client = httpx.Client(base_url=self.ollama_url, timeout=120)

    def detect_chapters(self, pdf_path: str) -> ChapterizerResult:
        document = fitz.open(pdf_path)
        try:
            page_texts: list[str] = []
            for page_index, page in enumerate(document, start=1):
                page_text = page.get_text("text")
                page_header = f"\n--- PAGE {page_index} ---\n"
                page_texts.append(page_header + page_text)
            combined_text = "\n".join(page_texts)
        finally:
            document.close()

        chapters = self._query_ollama_for_chapters(combined_text)
        if not chapters:
            chapters = self._regex_fallback(page_texts)

        return ChapterizerResult(chapters=chapters, raw_text=combined_text)

    def _query_ollama_for_chapters(self, text: str) -> list[ChapterInfo]:
        prompt = self._build_prompt(text)
        payload = {"model": self.model, "prompt": prompt}
        try:
            response = self._client.post("/api/generate", json=payload)
            response.raise_for_status()
        except httpx.HTTPError:
            return []
        try:
            data = response.json()
        except json.JSONDecodeError:
            return []
        raw = data.get("response") if isinstance(data, dict) else data
        if isinstance(raw, str):
            return self._parse_chapter_json(raw)
        return []

    def _parse_chapter_json(self, raw: str) -> list[ChapterInfo]:
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            match = re.search(r"\[(?:.|\n)*\]", raw)
            if not match:
                return []
            try:
                data = json.loads(match.group(0))
            except json.JSONDecodeError:
                return []
        chapters: list[ChapterInfo] = []
        if not isinstance(data, list):
            return []
        for item in data:
            try:
                chapters.append(ChapterInfo(**item))
            except ValidationError:
                continue
        return chapters

    def _regex_fallback(self, page_texts: list[str]) -> list[ChapterInfo]:
        heading_pattern = re.compile(r"^(?P<prefix>(?:[0-9]+\.|[A-Z]+))?\s*(?P<title>[A-ZÄÖÜ][A-ZÄÖÜ\s]{4,})$", re.MULTILINE)
        chapters: list[ChapterInfo] = []
        current_start = 1
        for index, page_text in enumerate(page_texts, start=1):
            for match in heading_pattern.finditer(page_text):
                title = match.group("title").strip().title()
                key = _guess_key_from_title(title)
                if chapters:
                    chapters[-1].page_end = index
                chapters.append(
                    ChapterInfo(
                        key=key,
                        title=title,
                        subtitle=None,
                        page_start=index,
                        page_end=index,
                    )
                )
                current_start = index
        if chapters:
            chapters[-1].page_end = len(page_texts)
        else:
            chapters.append(
                ChapterInfo(
                    key="SCOPE",
                    title="Gesamtdokument",
                    subtitle=None,
                    page_start=1,
                    page_end=len(page_texts),
                )
            )
        return chapters

    def _build_prompt(self, text: str) -> str:
        return (
            "Du analysierst einen technischen Bericht. Identifiziere die HAUPTKAPITEL und ihre Seitenbereiche.\n\n"
            "Antworte NUR als JSON-Array:\n"
            "[{\"key\": \"SEMANTIC_KEY\", \"title\": \"Original-Überschrift\", \"subtitle\": \"Untertitel oder null\", \"page_start\": N, \"page_end\": N}]\n\n"
            "Verfügbare SEMANTIC_KEYS (wähle den passendsten):\n"
            "- SCOPE: Untersuchungsgegenstand, Einleitung, Aufgabe, Gegenstand\n"
            "- MODEL: Berechnungsmodell, FEM-Modell, MKS-Modell, Systemmodell, Modellierung\n"
            "- RESULT: Ergebnisse, Nachweise, Spannungsnachweis, Nachrechnung\n"
            "- SUMM: Zusammenfassung, Summary, Fazit\n"
            "- APPEND: Anhang, Appendix, Anhänge\n"
            "- TEST: Prüfbericht, Laborergebnisse, Versuchsergebnisse, Messergebnisse\n"
            "- LOAD: Lastannahmen, Einwirkungen, Belastung\n"
            "- BASIS: Grundlagen, Normen, Standards, Vorbemerkungen\n"
            "- GEO: Geometrie, Abmessungen, Konstruktion\n\n"
            "Berichtstext:\n"
            f"{text}"
        )


def _guess_key_from_title(title: str) -> str:
    normalized = title.lower()
    mapping: list[tuple[str, str]] = [
        ("anhang", "APPEND"),
        ("appendix", "APPEND"),
        ("zusammenfassung", "SUMM"),
        ("summary", "SUMM"),
        ("fazit", "SUMM"),
        ("modell", "MODEL"),
        ("model", "MODEL"),
        ("ergebnis", "RESULT"),
        ("results", "RESULT"),
        ("versuch", "TEST"),
        ("test", "TEST"),
        ("last", "LOAD"),
        ("einwirkung", "LOAD"),
        ("grundlage", "BASIS"),
        ("norm", "BASIS"),
        ("geometrie", "GEO"),
        ("scope", "SCOPE"),
        ("einleitung", "SCOPE"),
    ]
    for needle, key in mapping:
        if needle in normalized:
            return key
    return "SCOPE"
