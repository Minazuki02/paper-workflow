"""Quality baseline for Phase 1 retrieval ranking and analysis-oriented filters."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from backend.common.db import initialize_database
from backend.common.models import Author, Chunk, Paper
from backend.retrieval.tools import handle_retrieve_evidence
from backend.storage.sqlite_store import SQLiteMetadataStore


class FakeEmbedder:
    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return [[0.9, 0.2, 0.7] for _ in texts]


class FakeVectorStore:
    metric = "cosine"
    size = 3

    def load(self) -> bool:
        return True

    def search(self, query_vector, *, top_k: int = 10):
        return [
            _RawHit("chunk-attention-main", 0.98),
            _RawHit("chunk-attention-variant", 0.76),
            _RawHit("chunk-planning", 0.10),
        ][:top_k]


class _RawHit:
    def __init__(self, chunk_id: str, score: float) -> None:
        self.chunk_id = chunk_id
        self.score = score


def test_hybrid_retrieval_ranks_attention_evidence_ahead_of_distractors() -> None:
    store = _seed_retrieval_store()

    result = handle_retrieve_evidence(
        query="attention mechanisms in the model",
        top_k=2,
        search_mode="hybrid",
        min_score=0.2,
        metadata_store=store,
        vector_store=FakeVectorStore(),
        embedder=FakeEmbedder(),
    )

    assert result["search_mode_used"] == "hybrid"
    assert result["total_candidates"] >= 2

    hits = result["hits"]
    assert [hit["chunk_id"] for hit in hits] == [
        "chunk-attention-main",
        "chunk-attention-variant",
    ]
    assert hits[0]["score"] >= hits[1]["score"] > 0.2
    assert "scaled dot-product attention" in hits[0]["text"].lower()
    assert hits[0]["paper_title"] == "Attention Mechanisms in Practice"


def test_retrieval_can_scope_methodology_evidence_for_single_paper_analysis() -> None:
    store = _seed_retrieval_store()

    result = handle_retrieve_evidence(
        query="how does the method use attention",
        top_k=3,
        search_mode="text",
        paper_ids=["paper-attention"],
        section_types=["methodology"],
        min_score=0.2,
        metadata_store=store,
        vector_store=FakeVectorStore(),
        embedder=FakeEmbedder(),
    )

    assert result["search_mode_used"] == "text"
    assert result["total_candidates"] >= 1
    assert [hit["chunk_id"] for hit in result["hits"]] == ["chunk-attention-main"]
    assert result["hits"][0]["section_type"] == "methodology"
    assert result["hits"][0]["paper_id"] == "paper-attention"


def _seed_retrieval_store() -> SQLiteMetadataStore:
    store = SQLiteMetadataStore(connection=initialize_database(db_path=":memory:"))

    store.upsert_paper(
        Paper(
            paper_id="paper-attention",
            title="Attention Mechanisms in Practice",
            authors=[Author(name="Alice Smith"), Author(name="Bob Jones")],
            year=2024,
            status="ready",
        )
    )
    store.upsert_paper(
        Paper(
            paper_id="paper-planning",
            title="Planning Agents Without Attention",
            authors=[Author(name="Carol Lee")],
            year=2023,
            status="ready",
        )
    )

    store.replace_chunks(
        "paper-attention",
        [
            Chunk(
                chunk_id="chunk-attention-main",
                paper_id="paper-attention",
                text=(
                    "Our methodology uses scaled dot-product attention and multi-head "
                    "attention as the main attention mechanisms in the model."
                ),
                char_count=121,
                order_index=0,
                page_start=3,
                section_type="methodology",
                heading="3 Methodology",
            ),
            Chunk(
                chunk_id="chunk-attention-variant",
                paper_id="paper-attention",
                text=(
                    "We compare additive attention with multiplicative attention "
                    "variants to study robustness."
                ),
                char_count=93,
                order_index=1,
                page_start=5,
                section_type="experiments",
                heading="4 Experiments",
            ),
        ],
    )
    store.replace_chunks(
        "paper-planning",
        [
            Chunk(
                chunk_id="chunk-planning",
                paper_id="paper-planning",
                text=(
                    "The planner decomposes tasks into subgoals and schedules tool use "
                    "without relying on attention modules."
                ),
                char_count=104,
                order_index=0,
                page_start=2,
                section_type="methodology",
                heading="2 Method",
            )
        ],
    )

    return store
