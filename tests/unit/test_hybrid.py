"""Unit tests for reciprocal-rank hybrid retrieval."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.common.models import RetrievalHit
from backend.retrieval.filters import SearchRun
from backend.retrieval.hybrid import reciprocal_rank_fuse


def test_reciprocal_rank_fuse_merges_and_reranks_results() -> None:
    vector_run = SearchRun(
        hits=[
            _hit("chunk-a", score=0.95, vector_score=0.95),
            _hit("chunk-b", score=0.70, vector_score=0.70),
        ],
        total_candidates=2,
    )
    text_run = SearchRun(
        hits=[
            _hit("chunk-b", score=1.0, text_score=1.0, highlights=["[attention] helps"]),
            _hit("chunk-c", score=0.5, text_score=0.5),
        ],
        total_candidates=2,
    )

    result = reciprocal_rank_fuse(vector_run, text_run, top_k=3)

    assert [hit.chunk_id for hit in result.hits] == ["chunk-b", "chunk-a", "chunk-c"]
    assert result.total_candidates == 3
    assert result.hits[0].vector_score == 0.70
    assert result.hits[0].text_score == 1.0
    assert result.hits[0].highlights == ["[attention] helps"]
    assert result.hits[0].score >= result.hits[1].score >= result.hits[2].score


def _hit(
    chunk_id: str,
    *,
    score: float,
    vector_score: float | None = None,
    text_score: float | None = None,
    highlights: list[str] | None = None,
) -> RetrievalHit:
    return RetrievalHit(
        chunk_id=chunk_id,
        paper_id=f"paper-{chunk_id}",
        text=f"Text for {chunk_id}",
        score=score,
        vector_score=vector_score,
        text_score=text_score,
        paper_title=f"Paper {chunk_id}",
        authors="Alice Smith",
        year=2024,
        section_type="methodology",
        heading="2 Methodology",
        page_start=2,
        highlights=highlights,
    )
