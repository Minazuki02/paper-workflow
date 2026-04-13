"""Hybrid retrieval utilities for combining vector and text search results."""

from __future__ import annotations

from backend.retrieval.filters import SearchRun

DEFAULT_RRF_K = 60


def reciprocal_rank_fuse(
    vector_run: SearchRun,
    text_run: SearchRun,
    *,
    top_k: int = 10,
    min_score: float = 0.0,
    rrf_k: int = DEFAULT_RRF_K,
) -> SearchRun:
    """Merge two ranked result lists with reciprocal rank fusion."""

    if top_k <= 0:
        return SearchRun(hits=[], total_candidates=0)

    fused_scores: dict[str, float] = {}
    merged_hits = {}

    for rank, hit in enumerate(vector_run.hits, start=1):
        fused_scores[hit.chunk_id] = fused_scores.get(hit.chunk_id, 0.0) + _rrf(rank, rrf_k)
        merged_hits[hit.chunk_id] = hit

    for rank, hit in enumerate(text_run.hits, start=1):
        fused_scores[hit.chunk_id] = fused_scores.get(hit.chunk_id, 0.0) + _rrf(rank, rrf_k)
        if hit.chunk_id in merged_hits:
            merged_hits[hit.chunk_id] = _merge_hits(merged_hits[hit.chunk_id], hit)
        else:
            merged_hits[hit.chunk_id] = hit

    if not fused_scores:
        return SearchRun(hits=[], total_candidates=0)

    peak_score = max(fused_scores.values())
    ordered_hits = []
    for chunk_id, raw_score in sorted(
        fused_scores.items(),
        key=lambda item: (-item[1], item[0]),
    ):
        merged = merged_hits[chunk_id]
        normalized_score = 0.0 if peak_score <= 0.0 else raw_score / peak_score
        if normalized_score < min_score:
            continue
        ordered_hits.append(
            merged.model_copy(
                update={
                    "score": normalized_score,
                    "highlights": _dedupe_highlights(merged.highlights),
                }
            )
        )
        if len(ordered_hits) >= top_k:
            break

    return SearchRun(hits=ordered_hits, total_candidates=len(fused_scores))


def _rrf(rank: int, rrf_k: int) -> float:
    return 1.0 / float(rrf_k + rank)


def _merge_hits(primary, secondary):
    return primary.model_copy(
        update={
            "score": max(primary.score, secondary.score),
            "vector_score": (
                secondary.vector_score if primary.vector_score is None else primary.vector_score
            ),
            "text_score": secondary.text_score if secondary.text_score is not None else primary.text_score,
            "highlights": _dedupe_highlights((primary.highlights or []) + (secondary.highlights or [])),
        }
    )


def _dedupe_highlights(highlights: list[str] | None) -> list[str] | None:
    if not highlights:
        return None
    unique = list(dict.fromkeys(highlights))
    return unique or None
