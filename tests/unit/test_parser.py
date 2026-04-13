"""Unit tests for the Phase 1 PyMuPDF parser skeleton."""

from __future__ import annotations

import sys
from pathlib import Path

import fitz

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.common.config import AppConfig
from backend.ingest.parser import extract_page_map, parse_pdf
from backend.storage.file_store import PdfFileStore


def test_parse_pdf_extracts_raw_text_and_page_count(tmp_path: Path) -> None:
    file_store = PdfFileStore(settings=_settings_for(tmp_path))
    pdf_path = _store_fixture_pdf(file_store)

    result = parse_pdf(pdf_path, paper_id="paper-1", file_store=file_store)

    assert result["paper_id"] == "paper-1"
    assert result["parser_used"] == "pymupdf"
    assert result["page_count"] == 2
    assert result["char_count"] > 0
    assert "Hello from page 1" in result["raw_text"]
    assert "Hello from page 2" in result["raw_text"]
    assert result["sections"] == []
    assert result["references_raw"] == []


def test_extract_page_map_tracks_page_offsets(tmp_path: Path) -> None:
    file_store = PdfFileStore(settings=_settings_for(tmp_path))
    pdf_path = _store_fixture_pdf(file_store)

    page_map = extract_page_map(pdf_path, file_store=file_store)

    assert [entry["page"] for entry in page_map] == [1, 2]
    assert page_map[0]["text"] == "Hello from page 1"
    assert page_map[1]["text"] == "Hello from page 2"
    assert page_map[0]["start_char"] == 0
    assert page_map[0]["end_char"] <= page_map[1]["start_char"]


def _store_fixture_pdf(file_store: PdfFileStore) -> str:
    document = fitz.open()
    page_one = document.new_page()
    page_one.insert_text((72, 72), "Hello from page 1")
    page_two = document.new_page()
    page_two.insert_text((72, 72), "Hello from page 2")
    pdf_bytes = document.tobytes()
    document.close()

    relative_path, _, _ = file_store.save_bytes(pdf_bytes)
    return relative_path


def _settings_for(tmp_path: Path) -> AppConfig:
    return AppConfig.model_validate(
        {
            "app": {"name": "paper-workflow-test"},
            "paths": {
                "data_dir": tmp_path / "data",
                "logs_dir": tmp_path / "data" / "logs",
                "db_path": tmp_path / "data" / "db" / "papers.db",
                "index_dir": tmp_path / "data" / "index",
                "pdf_dir": tmp_path / "data" / "pdfs",
            },
            "models": {"embedding_model": "all-MiniLM-L6-v2"},
            "logging": {"level": "INFO", "json": True},
        }
    )
