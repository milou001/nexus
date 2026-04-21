"""
INPUT:
- pdf_path: str — Path to the source PDF file.
- ollama_url: str — Base URL of the Ollama server.
- model: str — Ollama model used for chapter detection.
OUTPUT:
- ChapterizerResult containing detected chapters with page ranges and raw TOC text.
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


# ── Semantic key definitions ──────────────────────────────────────────

SEMANTIC_KEY_MAP: dict[str, str] = {
    # German → Key
    "zusammenfassung": "SUMM",
    "unterschriften": "SIGN",
    "angaben zum auftrag": "BILLING",
    "auftrag": "BILLING",
    "abrechnung": "BILLING",
    "aufwand": "BILLING",
    "untersuchungsgegenstand": "SCOPE",
    "gegenstand": "SCOPE",
    "einleitung": "SCOPE",
    "aufgabe": "SCOPE",
    "berechnungsmodell": "MODEL",
    "fem-modell": "MODEL",
    "mks-modell": "MODEL",
    "systemmodell": "MODEL",
    "modellierung": "MODEL",
    "modell": "MODEL",
    "ergebnisse": "RESULT",
    "ergebnis": "RESULT",
    "nachweise": "RESULT",
    "nachweis": "RESULT",
    "spannungsnachweis": "RESULT",
    "nachrechnung": "RESULT",
    "anhang": "APPEND",
    "anhänge": "APPEND",
    "appendix": "APPEND",
    "prüfbericht": "TEST",
    "laborergebnisse": "TEST",
    "versuchsergebnisse": "TEST",
    "messergebnisse": "TEST",
    "lastannahmen": "LOAD",
    "einwirkungen": "LOAD",
    "belastung": "LOAD",
    "grundlagen": "BASIS",
    "normen": "BASIS",
    "standards": "BASIS",
    "vorbemerkungen": "BASIS",
    "geometrie": "GEO",
    "abmessungen": "GEO",
    "konstruktion": "GEO",
    # English → Key
    "summary": "SUMM",
    "introduction": "SCOPE",
    "scope": "SCOPE",
    "model": "MODEL",
    "results": "RESULT",
    "appendix": "APPEND",
    "test": "TEST",
    "loading": "LOAD",
    "basis": "BASIS",
    "geometry": "GEO",
}

SEMANTIC_KEYS = set(SEMANTIC_KEY_MAP.values())


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
    toc_text: str


class Chapterizer:
    """Detects chapters by extracting the Inhaltsverzeichnis, then verifying via LLM."""

    def __init__(self, ollama_url: str | None = None, model: str | None = None) -> None:
        self.ollama_url = ollama_url or settings.ollama_url
        self.model = model or settings.chapter_model
        self._client = httpx.Client(base_url=self.ollama_url, timeout=120)

    def detect_chapters(self, pdf_path: str) -> ChapterizerResult:
        document = fitz.open(pdf_path)
        try:
            full_text = ""
            for page in document:
                full_text += page.get_text("text") + "\n"

            # Step 1: Extract TOC pages
            toc_text, toc_end_page = self._extract_toc(document)

            # Step 2: Parse headings from TOC
            headings = self._parse_toc_headings(toc_text)

            # Step 3: If TOC found headings, use them + LLM verification
            if headings:
                chapters = self._headings_to_chapters(headings, len(document), toc_end_page)
                # LLM verification: check headings match actual content
                verified = self._verify_chapters_llm(toc_text, chapters, document)
                if verified:
                    chapters = verified
            else:
                # Fallback: LLM-only or regex
                chapters = self._llm_fallback(full_text, len(document))
                if not chapters:
                    chapters = self._regex_fallback(document)

        finally:
            document.close()

        return ChapterizerResult(chapters=chapters, raw_text=full_text, toc_text=toc_text)

    # ── TOC Extraction ────────────────────────────────────────────────

    def _extract_toc(self, document: fitz.Document) -> tuple[str, int]:
        """
        Find pages containing 'Inhaltsverzeichnis' and extract all TOC text.
        Returns (toc_text, toc_end_page).
        """
        toc_pages: list[str] = []
        toc_start_page = 0
        toc_end_page = 0
        in_toc = False

        for page_index, page in enumerate(document, start=1):
            text = page.get_text("text")
            # Check if this page starts or continues the TOC
            if not in_toc and re.search(r"inhaltsverzeichnis", text, re.IGNORECASE):
                in_toc = True
                toc_start_page = page_index

            if in_toc:
                toc_pages.append(text)
                toc_end_page = page_index
                # TOC ends when we hit a main heading that's NOT part of TOC
                # (TOC entries have tab indentation, real headings don't)
                # We keep collecting until we see a page without TOC-like content
                lines = text.strip().split("\n")
                has_toc_entries = any(
                    "\t" in line or re.match(r"^\d+\.\s", line) for line in lines
                )
                if not has_toc_entries and page_index > toc_start_page:
                    # This page has no TOC entries — remove it, TOC ended before
                    toc_pages.pop()
                    toc_end_page = page_index - 1
                    break

        return "\n".join(toc_pages), toc_end_page

    def _parse_toc_headings(self, toc_text: str) -> list[dict[str, Any]]:
        """
        Parse Hauptüberschriften from TOC text.
        Main headings: single-digit number prefix, left-aligned (no leading tab).
        Sub-headings: indented with tab.
        """
        headings: list[dict[str, Any]] = []
        lines = toc_text.split("\n")

        for line in lines:
            line_stripped = line.strip()
            if not line_stripped:
                continue

            # Main heading: "1 Zusammenfassung .... 5" or "1. Zusammenfassung ... 5"
            # Single digit (1-9) followed by title and page number
            main_match = re.match(
                r"^(\d)\.?\s+(.+?)\s{2,}(\d+)\s*$",
                line_stripped,
            )
            if main_match:
                num = int(main_match.group(1))
                title = main_match.group(2).strip()
                page = int(main_match.group(3))
                # Skip "Inhaltsverzeichnis" itself
                if re.search(r"inhaltsverzeichnis", title, re.IGNORECASE):
                    continue
                headings.append({
                    "number": num,
                    "title": title,
                    "page": page,
                    "is_main": True,
                })
                continue

            # Alternative: main heading with tab-separated page number
            # "1\tZusammenfassung\t5"
            tab_match = re.match(
                r"^(\d)\.?\s+(.+?)\t+(\d+)\s*$",
                line_stripped,
            )
            if tab_match:
                num = int(tab_match.group(1))
                title = tab_match.group(2).strip()
                page = int(tab_match.group(3))
                if re.search(r"inhaltsverzeichnis", title, re.IGNORECASE):
                    continue
                headings.append({
                    "number": num,
                    "title": title,
                    "page": page,
                    "is_main": True,
                })

        return headings

    def _headings_to_chapters(
        self,
        headings: list[dict[str, Any]],
        total_pages: int,
        toc_end_page: int,
    ) -> list[ChapterInfo]:
        """Convert parsed TOC headings into ChapterInfo objects with page ranges."""
        chapters: list[ChapterInfo] = []

        for i, heading in enumerate(headings):
            if not heading.get("is_main"):
                continue

            page_start = heading["page"]
            # End page = start of next main heading - 1, or total pages
            if i + 1 < len(headings):
                page_end = headings[i + 1]["page"] - 1
            else:
                page_end = total_pages

            key = self._guess_key_from_title(heading["title"])

            chapters.append(ChapterInfo(
                key=key,
                title=heading["title"],
                subtitle=None,
                page_start=page_start,
                page_end=page_end,
            ))

        return chapters

    # ── LLM Verification ──────────────────────────────────────────────

    def _verify_chapters_llm(
        self,
        toc_text: str,
        chapters: list[ChapterInfo],
        document: fitz.Document,
    ) -> list[ChapterInfo] | None:
        """
        Send TOC + detected chapters to LLM for verification.
        LLM checks: correct semantic keys, correct page ranges, missing chapters.
        """
        chapters_desc = "\n".join(
            f"- {c.key}: \"{c.title}\" (S. {c.page_start}-{c.page_end})"
            for c in chapters
        )

        # Sample first few lines of each detected chapter page for verification
        samples = self._sample_chapter_pages(document, chapters)

        prompt = (
            "Du verifizierst die Kapitelerkennung eines technischen Berichts.\n\n"
            "INHALTSVERZEICHNIS:\n"
            f"{toc_text}\n\n"
            "ERKANNTE KAPITEL:\n"
            f"{chapters_desc}\n\n"
            "SEITENPROBEN (erste Zeilen der jeweiligen Startseiten):\n"
            f"{samples}\n\n"
            "Prüfe:\n"
            "1. Stimmen die SEMANTIC_KEYS? Korrigiere falls nötig.\n"
            "2. Stimmen die Seitenbereiche?\n"
            "3. Fehlt ein Hauptkapitel?\n\n"
            "Verfügbare KEYS:\n"
            "- SUMM: Zusammenfassung, Fazit\n"
            "- SIGN: Unterschriften\n"
            "- BILLING: Angaben zum Auftrag, Abrechnung, Aufwand\n"
            "- SCOPE: Untersuchungsgegenstand, Einleitung, Aufgabe\n"
            "- MODEL: Berechnungsmodell, FEM, MKS, Systemmodell\n"
            "- RESULT: Ergebnisse, Nachweise, Spannungsnachweis\n"
            "- APPEND: Anhang, Anhänge\n"
            "- TEST: Prüfbericht, Labor, Versuch, Messung\n"
            "- LOAD: Lastannahmen, Einwirkungen, Belastung\n"
            "- BASIS: Grundlagen, Normen, Standards\n"
            "- GEO: Geometrie, Abmessungen, Konstruktion\n\n"
            "Antworte NUR als JSON-Array:\n"
            '[{"key":"KEY","title":"Titel","subtitle":null,"page_start":N,"page_end":N}]'
        )

        payload = {"model": self.model, "prompt": prompt, "stream": False}
        try:
            response = self._client.post("/api/generate", json=payload)
            response.raise_for_status()
            data = response.json()
            raw = data.get("response", "")
            return self._parse_chapter_json(raw)
        except (httpx.HTTPError, json.JSONDecodeError):
            return None

    def _sample_chapter_pages(
        self, document: fitz.Document, chapters: list[ChapterInfo]
    ) -> str:
        """Extract first 5 lines of each chapter's start page for LLM verification."""
        samples: list[str] = []
        for ch in chapters:
            page_idx = ch.page_start - 1  # 0-based
            if 0 <= page_idx < len(document):
                text = document[page_idx].get_text("text")
                first_lines = "\n".join(text.strip().split("\n")[:5])
                samples.append(f"--- S. {ch.page_start} ({ch.title}) ---\n{first_lines}")
        return "\n\n".join(samples)

    # ── LLM Fallback ──────────────────────────────────────────────────

    def _llm_fallback(self, full_text: str, total_pages: int) -> list[ChapterInfo]:
        """Full LLM analysis when no TOC is found."""
        # Truncate to avoid context overflow
        truncated = full_text[:6000]
        prompt = (
            "Analysiere diesen technischen Bericht und identifiziere die HAUPTKAPITEL.\n\n"
            "Gesamtseitenzahl: " + str(total_pages) + "\n\n"
            "Berichtstext (Auszug):\n"
            f"{truncated}\n\n"
            "Antworte NUR als JSON-Array:\n"
            '[{"key":"KEY","title":"Titel","subtitle":null,"page_start":N,"page_end":N}]\n\n'
            "Verfügbare KEYS:\n"
            "- SUMM: Zusammenfassung, Fazit\n"
            "- SIGN: Unterschriften\n"
            "- BILLING: Angaben zum Auftrag, Abrechnung, Aufwand\n"
            "- SCOPE: Untersuchungsgegenstand, Einleitung, Aufgabe\n"
            "- MODEL: Berechnungsmodell, FEM, MKS, Systemmodell\n"
            "- RESULT: Ergebnisse, Nachweise, Spannungsnachweis\n"
            "- APPEND: Anhang, Anhänge\n"
            "- TEST: Prüfbericht, Labor, Versuch, Messung\n"
            "- LOAD: Lastannahmen, Einwirkungen, Belastung\n"
            "- BASIS: Grundlagen, Normen, Standards\n"
            "- GEO: Geometrie, Abmessungen, Konstruktion\n"
        )

        payload = {"model": self.model, "prompt": prompt, "stream": False}
        try:
            response = self._client.post("/api/generate", json=payload)
            response.raise_for_status()
            data = response.json()
            raw = data.get("response", "")
            return self._parse_chapter_json(raw)
        except (httpx.HTTPError, json.JSONDecodeError):
            return []

    # ── Regex Fallback ────────────────────────────────────────────────

    def _regex_fallback(self, document: fitz.Document) -> list[ChapterInfo]:
        """Last resort: find headings via font size / bold detection."""
        chapters: list[ChapterInfo] = []
        total_pages = len(document)

        for page_index, page in enumerate(document, start=1):
            blocks = page.get_text("dict")["blocks"]
            for block in blocks:
                if "lines" not in block:
                    continue
                for line in block["lines"]:
                    for span in line["spans"]:
                        # Bold + large font = likely main heading
                        if span["flags"] & 2**4:  # bold flag
                            text = span["text"].strip()
                            if text and len(text) > 3 and not text.startswith("Inhaltsverzeichnis"):
                                key = self._guess_key_from_title(text)
                                if chapters:
                                    chapters[-1].page_end = page_index
                                chapters.append(ChapterInfo(
                                    key=key,
                                    title=text,
                                    subtitle=None,
                                    page_start=page_index,
                                    page_end=total_pages,
                                ))

        if chapters:
            chapters[-1].page_end = total_pages
        else:
            chapters.append(ChapterInfo(
                key="SCOPE",
                title="Gesamtdokument",
                subtitle=None,
                page_start=1,
                page_end=total_pages,
            ))

        return chapters

    # ── Helpers ───────────────────────────────────────────────────────

    def _guess_key_from_title(self, title: str) -> str:
        normalized = title.lower().strip()
        # Check longest matches first for specificity
        for needle, key in sorted(SEMANTIC_KEY_MAP.items(), key=lambda x: -len(x[0])):
            if needle in normalized:
                return key
        return "SCOPE"

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
