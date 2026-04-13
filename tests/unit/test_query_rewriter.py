"""Unit tests for optional retrieval query rewriting."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from backend.common.config import AppConfig
from backend.common.db import initialize_database
from backend.common.models import Author, Chunk, Paper
from backend.retrieval.query_rewriter import RetrievalQueryRewriter
from backend.retrieval.tools import handle_retrieve_evidence
from backend.storage.sqlite_store import SQLiteMetadataStore


class FakeLLMClient:
    def complete(self, **_: object) -> str:
        return "multi-head attention mechanisms methodology"


class RecordingEmbedder:
    def __init__(self) -> None:
        self.last_texts: list[str] = []

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        self.last_texts = list(texts)
        return [[0.9, 0.1, 0.2] for _ in texts]


class FakeVectorStore:
    metric = "cosine"
    size = 1

    def load(self) -> bool:
        return True

    def search(self, query_vector, *, top_k: int = 10):
        return [type("Hit", (), {"chunk_id": "chunk-1", "score": 0.8})()]


def test_query_rewriter_uses_llm_when_enabled() -> None:
    settings = AppConfig.model_validate(
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
                "query_rewrite_enabled": True,
            },
        }
    )

    rewriter = RetrievalQueryRewriter(settings, client=FakeLLMClient())
    assert rewriter.rewrite("how does the model use attention?") == "multi-head attention mechanisms methodology"


def test_retrieve_evidence_uses_rewritten_query_for_vector_search() -> None:
    store = SQLiteMetadataStore(connection=initialize_database(db_path=":memory:"))
    store.upsert_paper(
        Paper(
            paper_id="paper-1",
            title="Attention Study",
            authors=[Author(name="Alice")],
            year=2024,
            status="ready",
        )
    )
    store.replace_chunks(
        "paper-1",
        [
            Chunk(
                chunk_id="chunk-1",
                paper_id="paper-1",
                text="The methodology relies on multi-head attention.",
                char_count=48,
                order_index=0,
                page_start=3,
                section_type="methodology",
                heading="3 Methodology",
            )
        ],
    )

    settings = AppConfig.model_validate(
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
                "query_rewrite_enabled": True,
            },
        }
    )

    embedder = RecordingEmbedder()
    rewriter = RetrievalQueryRewriter(settings, client=FakeLLMClient())

    result = handle_retrieve_evidence(
        query="how does the model use attention?",
        top_k=1,
        search_mode="vector",
        metadata_store=store,
        vector_store=FakeVectorStore(),
        embedder=embedder,
        query_rewriter=rewriter,
    )

    assert result["search_mode_used"] == "vector"
    assert embedder.last_texts == ["multi-head attention mechanisms methodology"]
