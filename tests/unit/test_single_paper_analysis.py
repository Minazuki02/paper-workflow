"""Unit coverage for LLM-backed single-paper analysis."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from backend.analysis.single_paper import SinglePaperAnalyzer, SinglePaperAnalysisError
from backend.common.config import AppConfig
from backend.common.db import initialize_database
from backend.common.models import Author, Chunk, Paper
from backend.storage.sqlite_store import SQLiteMetadataStore


class FakeLLMClient:
    def complete(self, **_: object) -> str:
        return """
        {
          "summary": "This paper studies practical attention mechanisms.",
          "contributions": ["Introduces an applied attention setup."],
          "methodology": "The method relies on multi-head attention in the core model.",
          "key_findings": ["Attention variants improve robustness in evaluation."],
          "limitations": ["Evidence is limited to a narrow benchmark."],
          "future_work": ["Expand evaluation across more datasets."]
        }
        """


class FakeEmbedder:
    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return [[0.9, 0.2, 0.4] for _ in texts]


class FakeVectorStore:
    metric = "cosine"
    size = 3

    def load(self) -> bool:
        return True

    def search(self, query_vector, *, top_k: int = 10):
        return [
            type("Hit", (), {"chunk_id": "chunk-method", "score": 0.94})(),
            type("Hit", (), {"chunk_id": "chunk-results", "score": 0.88})(),
            type("Hit", (), {"chunk_id": "chunk-limit", "score": 0.76})(),
        ][:top_k]


def test_single_paper_analyzer_returns_structured_analysis() -> None:
    store = _seed_analysis_store()
    settings = _settings()
    analyzer = SinglePaperAnalyzer(
        settings=settings,
        metadata_store=store,
        vector_store=FakeVectorStore(),
        embedder=FakeEmbedder(),
        llm_client=FakeLLMClient(),
    )

    response = analyzer.analyze(paper_id="paper-1", focus="methodology")

    assert response.result.paper_id == "paper-1"
    assert response.result.model_used == "glm-test"
    assert response.result.summary.startswith("This paper studies")
    assert response.result.contributions
    assert response.result.key_findings
    assert response.result.limitations
    assert response.result.evidence
    assert response.metrics.evidence_hits >= 1
    assert response.metrics.retrieval_queries >= 1


def test_single_paper_analyzer_requires_ready_paper() -> None:
    store = SQLiteMetadataStore(connection=initialize_database(db_path=":memory:"))
    store.upsert_paper(
        Paper(
            paper_id="paper-pending",
            title="Pending Paper",
            authors=[Author(name="Alice")],
            year=2025,
            status="queued",
        )
    )

    analyzer = SinglePaperAnalyzer(
        settings=_settings(),
        metadata_store=store,
        vector_store=FakeVectorStore(),
        embedder=FakeEmbedder(),
        llm_client=FakeLLMClient(),
    )

    try:
        analyzer.analyze(paper_id="paper-pending")
    except SinglePaperAnalysisError as exc:
        assert exc.error_code == "ANALYZE_PAPER_NOT_READY"
    else:  # pragma: no cover - defensive
        raise AssertionError("Expected ANALYZE_PAPER_NOT_READY to be raised.")


def _seed_analysis_store() -> SQLiteMetadataStore:
    store = SQLiteMetadataStore(connection=initialize_database(db_path=":memory:"))
    store.upsert_paper(
        Paper(
            paper_id="paper-1",
            title="Attention Mechanisms in Practice",
            authors=[Author(name="Alice Smith"), Author(name="Bob Jones")],
            abstract="A practical study of attention-based methods.",
            year=2024,
            status="ready",
        )
    )
    store.replace_chunks(
        "paper-1",
        [
            Chunk(
                chunk_id="chunk-method",
                paper_id="paper-1",
                text="Our methodology uses multi-head attention as the core mechanism.",
                char_count=64,
                order_index=0,
                page_start=3,
                section_type="methodology",
                heading="3 Methodology",
            ),
            Chunk(
                chunk_id="chunk-results",
                paper_id="paper-1",
                text="The evaluation shows improved robustness on downstream tasks.",
                char_count=61,
                order_index=1,
                page_start=5,
                section_type="experiments",
                heading="4 Experiments",
            ),
            Chunk(
                chunk_id="chunk-limit",
                paper_id="paper-1",
                text="A limitation is the narrow benchmark coverage used in experiments.",
                char_count=68,
                order_index=2,
                page_start=7,
                section_type="discussion",
                heading="5 Discussion",
            ),
        ],
    )
    return store


def _settings() -> AppConfig:
    return AppConfig.model_validate(
        {
            "app": {"name": "paper-workflow"},
            "paths": {
                "data_dir": "/tmp/data",
                "logs_dir": "/tmp/data/logs",
                "db_path": "/tmp/data/db/papers.db",
                "index_dir": "/tmp/data/index",
                "pdf_dir": "/tmp/data/pdfs",
            },
            "models": {"embedding_model": "all-MiniLM-L6-v2"},
            "llm": {
                "api_key": "test-key",
                "base_url": "https://example.invalid/v2",
                "model": "glm-test",
                "timeout": 30,
                "query_rewrite_enabled": False,
            },
        }
    )
