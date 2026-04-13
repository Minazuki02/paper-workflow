"""PyMuPDF-based PDF parsing skeleton for the Phase 1 ingest flow."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

import fitz

from backend.common.errors import PARSE_CORRUPT_PDF, PARSE_ENCRYPTED, PARSE_NO_TEXT
from backend.storage.file_store import PdfFileStore


class ParseError(Exception):
    """Structured parser failure aligned to the paper workflow error codes."""

    def __init__(self, error_code: str, message: str) -> None:
        super().__init__(message)
        self.error_code = error_code
        self.message = message


def parse_pdf(
    pdf_path: str | Path,
    *,
    paper_id: str,
    file_store: PdfFileStore | None = None,
) -> dict[str, Any]:
    """Extract raw text and basic parse metadata from a stored PDF."""

    resolved_path = _resolve_pdf_path(pdf_path, file_store=file_store)
    try:
        with fitz.open(resolved_path) as document:
            if document.needs_pass:
                raise ParseError(PARSE_ENCRYPTED, "PDF is encrypted and requires a password")

            page_text_map = extract_page_map(document)
            raw_text = "\n".join(entry["text"] for entry in page_text_map if entry["text"]).strip()
            if not raw_text:
                raise ParseError(PARSE_NO_TEXT, "PDF does not contain extractable text")

            return {
                "parse_id": str(uuid4()),
                "paper_id": paper_id,
                "parser_used": "pymupdf",
                "parsed_at": _utc_now_iso(),
                "page_count": document.page_count,
                "char_count": len(raw_text),
                "confidence": None,
                "has_ocr": False,
                "encoding_issues": False,
                "raw_text": raw_text,
                "sections": [],
                "references_raw": [],
            }
    except ParseError:
        raise
    except (fitz.FileDataError, fitz.EmptyFileError, RuntimeError, ValueError) as exc:
        raise ParseError(PARSE_CORRUPT_PDF, "PDF is corrupt or cannot be opened") from exc


def extract_page_map(
    source: str | Path | fitz.Document,
    *,
    file_store: PdfFileStore | None = None,
) -> list[dict[str, int | str]]:
    """Return per-page text with character offsets into the concatenated raw text."""

    if isinstance(source, fitz.Document):
        return _extract_page_map_from_document(source)

    resolved_path = _resolve_pdf_path(source, file_store=file_store)
    try:
        with fitz.open(resolved_path) as document:
            if document.needs_pass:
                raise ParseError(PARSE_ENCRYPTED, "PDF is encrypted and requires a password")
            return _extract_page_map_from_document(document)
    except ParseError:
        raise
    except (fitz.FileDataError, fitz.EmptyFileError, RuntimeError, ValueError) as exc:
        raise ParseError(PARSE_CORRUPT_PDF, "PDF is corrupt or cannot be opened") from exc


def _extract_page_map_from_document(document: fitz.Document) -> list[dict[str, int | str]]:
    page_map: list[dict[str, int | str]] = []
    cursor = 0

    for page_number, page in enumerate(document, start=1):
        page_text = _normalize_text(page.get_text("text"))
        start_char = cursor
        end_char = start_char + len(page_text)
        page_map.append(
            {
                "page": page_number,
                "start_char": start_char,
                "end_char": end_char,
                "text": page_text,
            }
        )
        cursor = end_char + 1

    return page_map


def _resolve_pdf_path(pdf_path: str | Path, *, file_store: PdfFileStore | None) -> Path:
    candidate = Path(pdf_path)
    if candidate.is_absolute():
        return candidate.expanduser().resolve()

    store = file_store or PdfFileStore()
    return store.get_absolute_path(candidate)


def _normalize_text(value: str) -> str:
    return "\n".join(line.rstrip() for line in value.replace("\x0c", "").splitlines()).strip()


def _utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
