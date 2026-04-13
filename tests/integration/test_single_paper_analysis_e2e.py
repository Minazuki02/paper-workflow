"""End-to-end coverage and timing assertions for single-paper analysis."""

from __future__ import annotations

import sys
from pathlib import Path
from time import perf_counter

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from backend.analysis.single_paper import SinglePaperAnalyzer
from backend.common.config import AppConfig
from backend.common.db import initialize_database
from backend.common.models import Author, Chunk, Paper
from backend.storage.sqlite_store import SQLiteMetadataStore


class FakeLLMClient:
    def complete(self, **_: object) -> str:
        return """
        {
          "summary": "This paper presents a practical study of attention.",
          "contributions": ["Provides a practical attention configuration."],
          "methodology": "The model relies on multi-head attention throughout the pipeline.",
          "key_findings": ["The paper reports robustness gains in evaluation."],
          "limitations": ["The benchmark scope remains narrow."],
          "future_work": ["Extend the evaluation to broader settings."]
        }
        """


class FakeEmbedder:
    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return [[0.7, 0.2, 0.9] for _ in texts]


class FakeVectorStore:
    metric = "cosine"
    size = 3

    def load(self) -> bool:
        return True

    def search(self, query_vector, *, top_k: int = 10):
        return [
            type("Hit", (), {"chunk_id": "chunk-method", "score": 0.92})(),
            type("Hit", (), {"chunk_id": "chunk-results", "score": 0.86})(),
            type("Hit", (), {"chunk_id": "chunk-limit", "score": 0.75})(),
        ][:top_k]


def test_single_paper_analysis_e2e_completes_within_local_budget() -> None:
    store = _seed_analysis_store()
    analyzer = SinglePaperAnalyzer(
        settings=_settings(),
        metadata_store=store,
        vector_store=FakeVectorStore(),
        embedder=FakeEmbedder(),
        llm_client=FakeLLMClient(),
    )

    started_at = perf_counter()
    response = analyzer.analyze(
        paper_id="paper-1",
        focus="methodology",
        user_query="How does this paper use attention?",
    )
    duration_ms = int(round((perf_counter() - started_at) * 1000))

    assert response.result.paper_id == "paper-1"
    assert response.result.summary
    assert response.result.methodology
    assert response.result.key_findings
    assert response.result.limitations
    assert response.metrics.evidence_hits >= 1
    assert response.metrics.retrieval_queries >= 1
    assert duration_ms < 2000


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
