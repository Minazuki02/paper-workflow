"""Unit tests for the Phase 1 PDF downloader and fetch_pdf handler."""

from __future__ import annotations

import sys
from io import BytesIO
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.common.config import AppConfig
from backend.ingest.downloader import (
    DOWNLOAD_NOT_PDF,
    DOWNLOAD_TIMEOUT,
    DOWNLOAD_TOO_LARGE,
    DownloadError,
    PdfDownloader,
)
from backend.ingest.tools import handle_fetch_pdf
from backend.storage.file_store import PdfFileStore

PDF_BYTES = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF"


class FakeResponse:
    def __init__(self, body: bytes, headers: dict[str, str]) -> None:
        self._stream = BytesIO(body)
        self.headers = headers

    def read(self, size: int = -1) -> bytes:
        return self._stream.read(size)

    def __enter__(self) -> FakeResponse:
        return self

    def __exit__(self, exc_type, exc, tb) -> bool | None:
        return None


def test_fetch_pdf_handler_returns_contract_and_deduplicates_downloads(tmp_path: Path) -> None:
    file_store = PdfFileStore(settings=_settings_for(tmp_path))
    downloader = PdfDownloader(
        file_store=file_store,
        fetcher=lambda _url, _timeout: FakeResponse(
            PDF_BYTES,
            {"Content-Type": "application/pdf", "Content-Length": str(len(PDF_BYTES))},
        ),
    )

    first = handle_fetch_pdf(url="https://example.com/paper.pdf", downloader=downloader)
    second = handle_fetch_pdf(url="https://example.com/paper.pdf", downloader=downloader)

    assert first == {
        "success": True,
        "pdf_path": first["pdf_path"],
        "file_size_bytes": len(PDF_BYTES),
        "pdf_hash": first["pdf_hash"],
        "already_exists": False,
    }
    assert second["success"] is True
    assert second["pdf_path"] == first["pdf_path"]
    assert second["pdf_hash"] == first["pdf_hash"]
    assert second["already_exists"] is True
    assert file_store.get_absolute_path(first["pdf_path"]).exists() is True


def test_downloader_retries_timeouts_and_raises_download_timeout(tmp_path: Path) -> None:
    attempts: list[str] = []

    def timeout_fetcher(_url: str, _timeout: float) -> FakeResponse:
        attempts.append("called")
        raise TimeoutError("boom")

    downloader = PdfDownloader(
        file_store=PdfFileStore(settings=_settings_for(tmp_path)),
        fetcher=timeout_fetcher,
        sleeper=lambda _delay: None,
        randomizer=lambda: 0.0,
    )

    with pytest.raises(DownloadError) as exc_info:
        downloader.download("https://example.com/paper.pdf")

    assert exc_info.value.error_code == DOWNLOAD_TIMEOUT
    assert len(attempts) == 3


def test_downloader_rejects_non_pdf_content(tmp_path: Path) -> None:
    downloader = PdfDownloader(
        file_store=PdfFileStore(settings=_settings_for(tmp_path)),
        fetcher=lambda _url, _timeout: FakeResponse(
            b"<html>not a pdf</html>",
            {"Content-Type": "text/html"},
        ),
    )

    with pytest.raises(DownloadError) as exc_info:
        downloader.download("https://example.com/not-pdf")

    assert exc_info.value.error_code == DOWNLOAD_NOT_PDF


def test_downloader_rejects_oversized_pdfs(tmp_path: Path) -> None:
    downloader = PdfDownloader(
        file_store=PdfFileStore(settings=_settings_for(tmp_path)),
        max_size_bytes=8,
        fetcher=lambda _url, _timeout: FakeResponse(
            PDF_BYTES,
            {"Content-Type": "application/pdf", "Content-Length": "999"},
        ),
    )

    with pytest.raises(DownloadError) as exc_info:
        downloader.download("https://example.com/large.pdf")

    assert exc_info.value.error_code == DOWNLOAD_TOO_LARGE


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
