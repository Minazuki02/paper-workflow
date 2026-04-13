"""MCP tool handlers for the Phase 1 retrieval backend."""

from __future__ import annotations

from time import perf_counter
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from backend.common.errors import (
    RETRIEVE_EMPTY_INDEX,
    RETRIEVE_INVALID_PAPER,
    RETRIEVE_MODEL_ERROR,
    RETRIEVE_QUERY_TOO_LONG,
    SYSTEM_INTERNAL_ERROR,
    build_tool_error,
)
from backend.common.models import SectionType
from backend.ingest.embedder import EmbedderError, SentenceTransformerEmbedder
from backend.retrieval.filters import (
    RetrievalFilters,
    SearchRun,
    count_ready_chunks,
    validate_paper_ids,
)
from backend.retrieval.hybrid import reciprocal_rank_fuse
from backend.retrieval.query_rewriter import RetrievalQueryRewriter
from backend.retrieval.text_search import TextSearcher
from backend.retrieval.vector_search import VectorSearcher
from backend.storage.faiss_store import FaissStore
from backend.storage.sqlite_store import SQLiteMetadataStore


class RetrieveEvidenceRequest(BaseModel):
    """Validated input payload for retrieve_evidence."""

    model_config = ConfigDict(extra="forbid")

    query: str = Field(min_length=1, max_length=2000)
    top_k: int = Field(default=10, ge=1, le=50)
    paper_ids: list[str] | None = None
    section_types: list[SectionType] | None = None
    year_from: int | None = None
    year_to: int | None = None
    search_mode: Literal["hybrid", "vector", "text"] = "hybrid"
    min_score: float = Field(default=0.3, ge=0.0, le=1.0)


def handle_retrieve_evidence(
    *,
    query: str,
    top_k: int = 10,
    paper_ids: list[str] | None = None,
    section_types: list[SectionType] | None = None,
    year_from: int | None = None,
    year_to: int | None = None,
    search_mode: str = "hybrid",
    min_score: float = 0.3,
    metadata_store: SQLiteMetadataStore | None = None,
    vector_store: FaissStore | None = None,
    embedder: SentenceTransformerEmbedder | None = None,
    query_rewriter: RetrievalQueryRewriter | None = None,
) -> dict[str, object]:
    """Retrieve evidence chunks from ready papers using vector/text/hybrid search."""

    try:
        request = RetrieveEvidenceRequest(
            query=query,
            top_k=top_k,
            paper_ids=paper_ids,
            section_types=section_types,
            year_from=year_from,
            year_to=year_to,
            search_mode=search_mode,
            min_score=min_score,
        )
    except ValidationError as exc:
        if any(error["loc"] == ("query",) for error in exc.errors(include_url=False)):
            return build_tool_error(
                RETRIEVE_QUERY_TOO_LONG,
                details={"validation_error": exc.errors(include_url=False)},
            ).model_dump()
        return build_tool_error(
            SYSTEM_INTERNAL_ERROR,
            error_message="Invalid retrieve_evidence parameters supplied.",
            retryable=False,
            details={"validation_error": exc.errors(include_url=False)},
        ).model_dump()

    store = metadata_store or SQLiteMetadataStore()
    rewritten_query = (query_rewriter or RetrievalQueryRewriter()).rewrite(request.query)
    filters = RetrievalFilters(
        paper_ids=None if request.paper_ids is None else tuple(request.paper_ids),
        section_types=None if request.section_types is None else tuple(request.section_types),
        year_from=request.year_from,
        year_to=request.year_to,
    )

    missing_paper_ids = validate_paper_ids(store.connection, request.paper_ids)
    if missing_paper_ids:
        return build_tool_error(
            RETRIEVE_INVALID_PAPER,
            details={"missing_paper_ids": missing_paper_ids},
        ).model_dump()

    if count_ready_chunks(store.connection, filters=filters) == 0:
        return build_tool_error(
            RETRIEVE_EMPTY_INDEX,
            details={"paper_ids": request.paper_ids, "section_types": request.section_types},
        ).model_dump()

    query_embedding_ms = 0
    search_ms = 0

    resolved_vector_store = vector_store or FaissStore()
    resolved_embedder = embedder or SentenceTransformerEmbedder()
    vector_searcher = VectorSearcher(
        metadata_store=store,
        vector_store=resolved_vector_store,
        embedder=resolved_embedder,
    )
    text_searcher = TextSearcher(metadata_store=store)

    try:
        if request.search_mode == "vector":
            if not vector_searcher.has_index():
                return build_tool_error(RETRIEVE_EMPTY_INDEX).model_dump()
            embed_started = perf_counter()
            query_vector = vector_searcher.embed_query(rewritten_query)
            query_embedding_ms = _elapsed_ms(embed_started)

            search_started = perf_counter()
            run = vector_searcher.search_by_vector(
                query_vector,
                top_k=request.top_k,
                filters=filters,
                min_score=request.min_score,
            )
            search_ms = _elapsed_ms(search_started)
            search_mode_used = "vector"

        elif request.search_mode == "text":
            search_started = perf_counter()
            run = text_searcher.search(
                rewritten_query,
                top_k=request.top_k,
                filters=filters,
                min_score=request.min_score,
            )
            search_ms = _elapsed_ms(search_started)
            search_mode_used = "text"

        else:
            vector_run = None
            query_vector = None
            if vector_searcher.has_index():
                embed_started = perf_counter()
                query_vector = vector_searcher.embed_query(rewritten_query)
                query_embedding_ms = _elapsed_ms(embed_started)

            search_started = perf_counter()
            if query_vector is not None:
                vector_run = vector_searcher.search_by_vector(
                    query_vector,
                    top_k=max(request.top_k * 5, request.top_k),
                    filters=filters,
                    min_score=0.0,
                )
            text_run = text_searcher.search(
                rewritten_query,
                top_k=max(request.top_k * 5, request.top_k),
                filters=filters,
                min_score=0.0,
            )
            search_ms = _elapsed_ms(search_started)

            if vector_run is None:
                run = SearchRun(
                    hits=[
                        hit for hit in text_run.hits if hit.score >= request.min_score
                    ][: request.top_k],
                    total_candidates=text_run.total_candidates,
                )
                search_mode_used = "text"
            elif text_run.total_candidates == 0:
                run = SearchRun(
                    hits=[
                        hit for hit in vector_run.hits if hit.score >= request.min_score
                    ][: request.top_k],
                    total_candidates=vector_run.total_candidates,
                )
                search_mode_used = "vector"
            else:
                run = reciprocal_rank_fuse(
                    vector_run,
                    text_run,
                    top_k=request.top_k,
                    min_score=request.min_score,
                )
                search_mode_used = "hybrid"

    except EmbedderError as exc:
        return build_tool_error(
            RETRIEVE_MODEL_ERROR,
            error_message=str(exc),
            details={"source_error_code": exc.error_code},
        ).model_dump()
    except Exception as exc:  # pragma: no cover - defensive fallback
        return build_tool_error(
            SYSTEM_INTERNAL_ERROR,
            details={"exception_type": type(exc).__name__},
        ).model_dump()

    return {
        "hits": [hit.model_dump() for hit in run.hits],
        "total_candidates": run.total_candidates,
        "search_mode_used": search_mode_used,
        "query_embedding_ms": query_embedding_ms,
        "search_ms": search_ms,
    }


def _elapsed_ms(started_at: float) -> int:
    return max(0, int(round((perf_counter() - started_at) * 1000)))
