"""Unit tests for the single-paper ingest pipeline."""

from __future__ import annotations

import sys
from pathlib import Path

import fitz

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.common.config import AppConfig
from backend.common.db import initialize_database
from backend.common.models import IngestOptions
from backend.ingest.deduplicator import PaperDeduplicator
from backend.ingest.embedder import EmbedderError
from backend.ingest.indexer import PaperIndexer
from backend.ingest.pipeline import PipelineFailure, SinglePaperIngestPipeline
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
        self._loaded = False
        self.dimension: int | None = None
        self.metric = "cosine"
        self.vectors: dict[str, list[float]] = {}
        self.removed_batches: list[list[str]] = []
        self.created_dimensions: list[int] = []

    @property
    def size(self) -> int:
        return len(self.vectors)

    def load(self) -> bool:
        self._loaded = True
        return bool(self.vectors)

    def create(self, dimension: int, *, metric: str = "cosine") -> None:
        self.dimension = dimension
        self.metric = metric
        self.created_dimensions.append(dimension)

    def add(self, chunk_ids: list[str], vectors: list[list[float]]) -> None:
        if vectors:
            incoming_dimension = len(vectors[0])
            if self.dimension is None:
                self.dimension = incoming_dimension
            elif self.dimension != incoming_dimension:
                raise ValueError(
                    f"Vector dimension mismatch: expected {self.dimension}, received {incoming_dimension}."
                )
        for chunk_id, vector in zip(chunk_ids, vectors, strict=True):
            self.vectors[chunk_id] = list(vector)

    def remove(self, chunk_ids: list[str]) -> int:
        removed = 0
        for chunk_id in chunk_ids:
            if self.vectors.pop(chunk_id, None) is not None:
                removed += 1
        if chunk_ids:
            self.removed_batches.append(list(chunk_ids))
        return removed

    def save(self) -> None:
        return None


class FailingEmbedder(FakeEmbedder):
    def embed_chunks(self, chunks) -> list[list[float]]:
        raise EmbedderError("EMBED_MODEL_UNAVAILABLE", "Embedding backend is unavailable.")


def test_pipeline_ingests_local_pdf_to_ready_and_writes_observability_artifacts(tmp_path: Path) -> None:
    settings = _settings_for(tmp_path)
    store = SQLiteMetadataStore(connection=initialize_database(db_path=":memory:"))
    file_store = PdfFileStore(settings=settings)
    vector_store = FakeVectorStore()

    pipeline = SinglePaperIngestPipeline(
        settings=settings,
        metadata_store=store,
        file_store=file_store,
        embedder=FakeEmbedder(),
        indexer=PaperIndexer(store, vector_store),
        deduplicator=PaperDeduplicator(store),
    )

    local_pdf = _create_sample_pdf(tmp_path / "sample.pdf")
    result = pipeline.ingest_from_local(local_pdf, source_url="https://example.com/papers/agent-workflow")

    assert result.skipped is False
    assert result.job.status == "completed"
    assert result.paper.status == "ready"
    assert result.paper.ingested_at is not None
    assert result.paper.chunk_count > 0
    assert result.paper.section_count >= 3
    assert store.get_chunks(result.paper.paper_id)
    assert store.get_sections(result.paper.paper_id)

    parse_metrics = store.connection.execute(
        "SELECT * FROM parse_metrics WHERE paper_id = ?",
        (result.paper.paper_id,),
    ).fetchone()
    assert parse_metrics is not None
    assert parse_metrics["section_count"] == result.paper.section_count

    trace_events = store.connection.execute(
        "SELECT stage, event FROM paper_traces WHERE paper_id = ? ORDER BY trace_id ASC",
        (result.paper.paper_id,),
    ).fetchall()
    trace_pairs = {(row["stage"], row["event"]) for row in trace_events}
    assert ("downloading", "stage_start") in trace_pairs
    assert ("parsing", "stage_end") in trace_pairs
    assert ("ready", "stage_end") in trace_pairs

    log_files = list(settings.paths.ingest_logs_dir.glob("*.jsonl"))
    assert log_files
    assert any("stage_end" in path.read_text(encoding="utf-8") for path in log_files)


def test_pipeline_skips_existing_paper_by_default(tmp_path: Path) -> None:
    settings = _settings_for(tmp_path)
    store = SQLiteMetadataStore(connection=initialize_database(db_path=":memory:"))
    file_store = PdfFileStore(settings=settings)
    vector_store = FakeVectorStore()

    pipeline = SinglePaperIngestPipeline(
        settings=settings,
        metadata_store=store,
        file_store=file_store,
        embedder=FakeEmbedder(),
        indexer=PaperIndexer(store, vector_store),
        deduplicator=PaperDeduplicator(store),
    )

    local_pdf = _create_sample_pdf(tmp_path / "sample.pdf")
    first = pipeline.ingest_from_local(local_pdf, source_url="https://example.com/papers/agent-workflow")
    second = pipeline.ingest_from_local(local_pdf, source_url="https://example.com/papers/agent-workflow")

    assert first.paper.paper_id == second.paper.paper_id
    assert second.skipped is True
    assert second.skip_reason == "existing_paper"
    assert second.job.skipped == 1


def test_pipeline_force_reparse_reuses_paper_and_replaces_existing_vectors(tmp_path: Path) -> None:
    settings = _settings_for(tmp_path)
    store = SQLiteMetadataStore(connection=initialize_database(db_path=":memory:"))
    file_store = PdfFileStore(settings=settings)
    vector_store = FakeVectorStore()

    pipeline = SinglePaperIngestPipeline(
        settings=settings,
        metadata_store=store,
        file_store=file_store,
        embedder=FakeEmbedder(),
        indexer=PaperIndexer(store, vector_store),
        deduplicator=PaperDeduplicator(store),
    )

    local_pdf = _create_sample_pdf(tmp_path / "sample.pdf")
    first = pipeline.ingest_from_local(local_pdf, source_url="https://example.com/papers/agent-workflow")
    second = pipeline.ingest_from_local(
        local_pdf,
        source_url="https://example.com/papers/agent-workflow",
        options=IngestOptions(skip_existing=False, force_reparse=True),
    )

    assert second.skipped is False
    assert second.paper.paper_id == first.paper.paper_id
    assert second.paper.status == "ready"
    assert vector_store.removed_batches
    assert len(store.get_chunks(second.paper.paper_id)) == second.paper.chunk_count


def test_pipeline_maps_stage_and_error_code_on_failure(tmp_path: Path) -> None:
    settings = _settings_for(tmp_path)
    store = SQLiteMetadataStore(connection=initialize_database(db_path=":memory:"))
    file_store = PdfFileStore(settings=settings)

    pipeline = SinglePaperIngestPipeline(
        settings=settings,
        metadata_store=store,
        file_store=file_store,
        embedder=FailingEmbedder(),
        indexer=PaperIndexer(store, FakeVectorStore()),
        deduplicator=PaperDeduplicator(store),
    )

    local_pdf = _create_sample_pdf(tmp_path / "sample.pdf")

    try:
        pipeline.ingest_from_local(local_pdf, source_url="https://example.com/papers/agent-workflow")
    except PipelineFailure as exc:
        assert exc.ingest_error.stage == "embedding"
        assert exc.ingest_error.error_code == "EMBED_MODEL_UNAVAILABLE"
        assert exc.job.status == "failed"
        assert exc.paper is not None
        assert exc.paper.status == "failed"
    else:
        raise AssertionError("Expected the ingest pipeline to raise PipelineFailure.")


def test_pipeline_force_reparse_recreates_empty_index_when_embedding_dimension_changes(tmp_path: Path) -> None:
    settings = _settings_for(tmp_path)
    store = SQLiteMetadataStore(connection=initialize_database(db_path=":memory:"))
    file_store = PdfFileStore(settings=settings)
    vector_store = FakeVectorStore()

    pipeline = SinglePaperIngestPipeline(
        settings=settings,
        metadata_store=store,
        file_store=file_store,
        embedder=FakeEmbedder(),
        indexer=PaperIndexer(store, vector_store),
        deduplicator=PaperDeduplicator(store),
    )

    local_pdf = _create_sample_pdf(tmp_path / "sample.pdf")
    first = pipeline.ingest_from_local(local_pdf, source_url="https://example.com/papers/agent-workflow")

    vector_store.dimension = 384

    class DifferentDimensionEmbedder(FakeEmbedder):
        model_name = "remote-embedding-model"

        def embed_chunks(self, chunks) -> list[list[float]]:
            return [[0.1, 0.2, 0.3, 0.4] for _ in chunks]

    reparsed = SinglePaperIngestPipeline(
        settings=settings,
        metadata_store=store,
        file_store=file_store,
        embedder=DifferentDimensionEmbedder(),
        indexer=PaperIndexer(store, vector_store),
        deduplicator=PaperDeduplicator(store),
    ).ingest_from_local(
        local_pdf,
        source_url="https://example.com/papers/agent-workflow",
        options=IngestOptions(skip_existing=False, force_reparse=True),
    )

    assert reparsed.paper.paper_id == first.paper.paper_id
    assert vector_store.dimension == 4
    assert vector_store.created_dimensions[-1] == 4


def _create_sample_pdf(path: Path) -> Path:
    text_blocks = (
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
                "We validate the workflow with deterministic unit tests.",
                "4 Conclusion",
                "The system reaches ready state with traceability.",
            ]
        ),
    )

    document = fitz.open()
    for block in text_blocks:
        page = document.new_page()
        page.insert_textbox((72, 72, 520, 760), block, fontsize=12)
    path.parent.mkdir(parents=True, exist_ok=True)
    document.save(path)
    document.close()
    return path


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
