"""Contract tests for the Phase 1 retrieval MCP tool surface."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.common.db import initialize_database
from backend.common.models import Author, Chunk, Paper
from backend.retrieval.mcp_server import create_server
from backend.retrieval.tools import handle_retrieve_evidence
from backend.storage.sqlite_store import SQLiteMetadataStore


class FakeEmbedder:
    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return [[0.6, 0.4, 0.9]]


class FakeVectorStore:
    metric = "cosine"

    def __init__(self) -> None:
        self.size = 1

    def load(self) -> bool:
        return True

    def search(self, query_vector, *, top_k: int = 10):
        return [type("Hit", (), {"chunk_id": "chunk-1", "score": 0.9})()]


def test_server_registers_only_retrieve_evidence_for_task25() -> None:
    server = create_server()
    tools = asyncio.run(server.list_tools())
    tool_names = {tool.name for tool in tools}

    assert "retrieve_evidence" in tool_names
    assert "reindex_paper" not in tool_names


def test_retrieve_evidence_output_schema_contains_retrieval_hit_fields() -> None:
    store = SQLiteMetadataStore(connection=initialize_database(db_path=":memory:"))
    _seed_records(store)

    result = handle_retrieve_evidence(
        query="agent planning evidence",
        top_k=1,
        search_mode="vector",
        metadata_store=store,
        vector_store=FakeVectorStore(),
        embedder=FakeEmbedder(),
    )

    assert "hits" in result
    assert result["search_mode_used"] == "vector"
    assert result["total_candidates"] == 1
    assert result["query_embedding_ms"] >= 0
    assert result["search_ms"] >= 0

    hit = result["hits"][0]
    for field in (
        "chunk_id",
        "paper_id",
        "text",
        "score",
        "paper_title",
        "authors",
    ):
        assert field in hit


def test_retrieve_evidence_returns_tool_error_for_invalid_paper_id() -> None:
    store = SQLiteMetadataStore(connection=initialize_database(db_path=":memory:"))
    _seed_records(store)

    result = handle_retrieve_evidence(
        query="agent planning evidence",
        paper_ids=["missing-paper"],
        metadata_store=store,
        search_mode="text",
    )

    assert result["error"] is True
    assert result["error_code"] == "RETRIEVE_INVALID_PAPER"
    assert "error_message" in result
    assert "retryable" in result


def _seed_records(store: SQLiteMetadataStore) -> None:
    store.upsert_paper(
        Paper(
            paper_id="paper-1",
            title="Agent Planning in Practice",
            authors=[Author(name="Alice Smith"), Author(name="Bob Jones")],
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
                text="Agent planning evidence appears in the methodology section.",
                char_count=59,
                order_index=0,
                page_start=2,
                section_type="methodology",
                heading="2 Methodology",
            )
        ],
    )
