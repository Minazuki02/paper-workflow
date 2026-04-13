"""Unit tests for retrieval full-text search."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.common.db import initialize_database
from backend.common.models import Author, Chunk, Paper
from backend.retrieval.filters import RetrievalFilters
from backend.retrieval.text_search import TextSearcher
from backend.storage.sqlite_store import SQLiteMetadataStore


def test_text_search_returns_highlighted_ranked_hits() -> None:
    store = SQLiteMetadataStore(connection=initialize_database(db_path=":memory:"))
    _seed_records(store)
    searcher = TextSearcher(metadata_store=store)

    result = searcher.search("multi-head attention mechanism", top_k=2)

    assert [hit.chunk_id for hit in result.hits] == ["chunk-attn", "chunk-compare"]
    assert result.total_candidates == 2
    assert result.hits[0].text_score > result.hits[1].text_score
    assert result.hits[0].highlights is not None
    assert any("attention" in snippet.lower() for snippet in result.hits[0].highlights or [])


def test_text_search_respects_section_filters() -> None:
    store = SQLiteMetadataStore(connection=initialize_database(db_path=":memory:"))
    _seed_records(store)
    searcher = TextSearcher(metadata_store=store)

    result = searcher.search(
        "attention mechanism",
        filters=RetrievalFilters(section_types=("conclusion",)),
    )

    assert result.hits == []
    assert result.total_candidates == 0


def _seed_records(store: SQLiteMetadataStore) -> None:
    store.upsert_paper(
        Paper(
            paper_id="paper-1",
            title="Transformers for Planning",
            authors=[Author(name="Dana Zhou")],
            year=2024,
            status="ready",
        )
    )
    store.replace_chunks(
        "paper-1",
        [
            Chunk(
                chunk_id="chunk-attn",
                paper_id="paper-1",
                text="The multi-head attention mechanism improves sequence modeling.",
                char_count=63,
                order_index=0,
                page_start=5,
                section_type="methodology",
                heading="2 Methodology",
            ),
            Chunk(
                chunk_id="chunk-compare",
                paper_id="paper-1",
                text="Compared with recurrent models, the attention mechanism is easier to parallelize.",
                char_count=86,
                order_index=1,
                page_start=6,
                section_type="experiments",
                heading="3 Results",
            ),
        ],
    )
