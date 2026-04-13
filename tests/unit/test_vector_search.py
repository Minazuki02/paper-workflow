"""Unit tests for retrieval vector search."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.common.db import initialize_database
from backend.common.models import Author, Chunk, Paper
from backend.retrieval.filters import RetrievalFilters
from backend.retrieval.vector_search import VectorSearcher
from backend.storage.sqlite_store import SQLiteMetadataStore


class FakeEmbedder:
    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        assert texts == ["agent planning"]
        return [[0.4, 0.9, 0.2]]


class FakeVectorStore:
    metric = "cosine"

    def __init__(self) -> None:
        self.size = 3
        self.loaded = False

    def load(self) -> bool:
        self.loaded = True
        return True

    def search(self, query_vector, *, top_k: int = 10):
        assert query_vector == [0.4, 0.9, 0.2]
        return [
            type("Hit", (), {"chunk_id": "chunk-method", "score": 0.92})(),
            type("Hit", (), {"chunk_id": "chunk-exp", "score": 0.36})(),
            type("Hit", (), {"chunk_id": "chunk-old", "score": -0.10})(),
        ][:top_k]


def test_vector_search_returns_ranked_hits_with_metadata() -> None:
    store = SQLiteMetadataStore(connection=initialize_database(db_path=":memory:"))
    _seed_records(store)
    searcher = VectorSearcher(
        metadata_store=store,
        vector_store=FakeVectorStore(),
        embedder=FakeEmbedder(),
    )

    result = searcher.search("agent planning", top_k=2)

    assert [hit.chunk_id for hit in result.hits] == ["chunk-method", "chunk-exp"]
    assert result.total_candidates == 3
    assert result.hits[0].score > result.hits[1].score
    assert result.hits[0].paper_title == "Agent Planning in Practice"
    assert result.hits[0].authors == "Alice Smith, Bob Jones"


def test_vector_search_applies_metadata_filters_after_faiss_lookup() -> None:
    store = SQLiteMetadataStore(connection=initialize_database(db_path=":memory:"))
    _seed_records(store)
    searcher = VectorSearcher(
        metadata_store=store,
        vector_store=FakeVectorStore(),
        embedder=FakeEmbedder(),
    )

    result = searcher.search(
        "agent planning",
        top_k=5,
        filters=RetrievalFilters(year_from=2024, section_types=("methodology",)),
    )

    assert [hit.chunk_id for hit in result.hits] == ["chunk-method"]
    assert result.total_candidates == 1


def _seed_records(store: SQLiteMetadataStore) -> None:
    store.upsert_paper(
        Paper(
            paper_id="paper-2024",
            title="Agent Planning in Practice",
            authors=[Author(name="Alice Smith"), Author(name="Bob Jones")],
            year=2024,
            status="ready",
        )
    )
    store.upsert_paper(
        Paper(
            paper_id="paper-2023",
            title="Older Attention Study",
            authors=[Author(name="Carol Lee")],
            year=2023,
            status="ready",
        )
    )
    store.replace_chunks(
        "paper-2024",
        [
            Chunk(
                chunk_id="chunk-method",
                paper_id="paper-2024",
                text="We plan agents with retrieval-aware search.",
                char_count=44,
                order_index=0,
                page_start=2,
                section_type="methodology",
                heading="2 Methodology",
            ),
            Chunk(
                chunk_id="chunk-exp",
                paper_id="paper-2024",
                text="Experiments confirm better planning accuracy.",
                char_count=44,
                order_index=1,
                page_start=4,
                section_type="experiments",
                heading="3 Experiments",
            ),
        ],
    )
    store.replace_chunks(
        "paper-2023",
        [
            Chunk(
                chunk_id="chunk-old",
                paper_id="paper-2023",
                text="Legacy attention baselines remain strong.",
                char_count=39,
                order_index=0,
                page_start=1,
                section_type="methodology",
                heading="1 Methods",
            )
        ],
    )
