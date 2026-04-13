"""Minimal integration coverage for ingest_paper and get_ingest_status."""

from __future__ import annotations

import socket
import sys
import threading
from contextlib import contextmanager
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import fitz

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.common.config import AppConfig
from backend.common.db import initialize_database
from backend.ingest.deduplicator import PaperDeduplicator
from backend.ingest.indexer import PaperIndexer
from backend.ingest.pipeline import SinglePaperIngestPipeline
from backend.ingest.tools import handle_get_ingest_status, handle_ingest_paper
from backend.storage.file_store import PdfFileStore
from backend.storage.sqlite_store import SQLiteMetadataStore


class FakeEmbedder:
    model_name = "fake-mini-embedder"

    def embed_chunks(self, chunks) -> list[list[float]]:
        vectors: list[list[float]] = []
        for index, chunk in enumerate(chunks, start=1):
            vectors.append(
                [
                    float(len(chunk.text)),
                    float(chunk.token_count or 0),
                    float(index),
                ]
            )
        return vectors


class FakeVectorStore:
    def __init__(self) -> None:
        self.vectors: dict[str, list[float]] = {}

    def load(self) -> bool:
        return bool(self.vectors)

    def add(self, chunk_ids: list[str], vectors: list[list[float]]) -> None:
        for chunk_id, vector in zip(chunk_ids, vectors, strict=True):
            self.vectors[chunk_id] = list(vector)

    def remove(self, chunk_ids: list[str]) -> int:
        removed = 0
        for chunk_id in chunk_ids:
            if self.vectors.pop(chunk_id, None) is not None:
                removed += 1
        return removed

    def save(self) -> None:
        return None


def test_ingest_paper_and_get_ingest_status_round_trip(tmp_path: Path) -> None:
    settings = _settings_for(tmp_path)
    store = SQLiteMetadataStore(connection=initialize_database(db_path=":memory:"))
    file_store = PdfFileStore(settings=settings)
    pipeline = SinglePaperIngestPipeline(
        settings=settings,
        metadata_store=store,
        file_store=file_store,
        embedder=FakeEmbedder(),
        indexer=PaperIndexer(store, FakeVectorStore()),
        deduplicator=PaperDeduplicator(store),
    )

    served_pdf = _create_sample_pdf(tmp_path / "served" / "paper.pdf")
    with serve_directory(served_pdf.parent) as base_url:
        ingest_result = handle_ingest_paper(
            url=f"{base_url}/{served_pdf.name}",
            pipeline=pipeline,
        )

    assert ingest_result["status"] == "queued"
    assert ingest_result["paper_id"] is None

    job_id = str(ingest_result["job_id"])
    job_status = handle_get_ingest_status(job_id=job_id, metadata_store=store)

    assert job_status["job"] is not None
    assert job_status["paper"] is None
    assert job_status["job"]["status"] == "completed"
    assert job_status["current_stage"] == "ready"
    assert job_status["errors"] == []
    assert job_status["retry_count"] == 0

    paper_id = str(job_status["job"]["paper_ids"][0])
    paper_status = handle_get_ingest_status(paper_id=paper_id, metadata_store=store)

    assert paper_status["job"] is None
    assert paper_status["paper"]["paper_id"] == paper_id
    assert paper_status["paper"]["status"] == "ready"
    assert paper_status["paper"]["chunk_count"] > 0
    assert paper_status["paper"]["section_count"] >= 3
    assert paper_status["current_stage"] == "ready"
    assert paper_status["errors"] == []
    assert paper_status["retry_count"] == 0


def _create_sample_pdf(path: Path) -> Path:
    pages = (
        "\n".join(
            [
                "Adaptive Agent Planning for Literature Review",
                "Alice Smith, Bob Jones",
                "2024",
                "Abstract",
                "We present a lightweight planning workflow for ingesting academic papers.",
                "1 Introduction",
                "This workflow keeps orchestration outside the storage layer.",
            ]
        ),
        "\n".join(
            [
                "2 Methodology",
                "The pipeline downloads, parses, chunks, embeds, and indexes each paper.",
                "3 Experiments",
                "We validate the workflow with deterministic integration tests.",
                "4 Conclusion",
                "The system reaches ready state with traceability.",
            ]
        ),
    )

    document = fitz.open()
    for page_text in pages:
        page = document.new_page()
        page.insert_textbox((72, 72, 520, 760), page_text, fontsize=12)
    path.parent.mkdir(parents=True, exist_ok=True)
    document.save(path)
    document.close()
    return path


def _settings_for(tmp_path: Path) -> AppConfig:
    return AppConfig.model_validate(
        {
            "app": {"name": "paper-ingest-e2e"},
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


@contextmanager
def serve_directory(directory: Path):
    class QuietHandler(SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(directory), **kwargs)

        def log_message(self, format: str, *args) -> None:  # noqa: A003
            return None

    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        host, port = sock.getsockname()

    server = ThreadingHTTPServer((host, port), QuietHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://{host}:{port}"
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()
