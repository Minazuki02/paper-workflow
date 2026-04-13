"""Shared metadata filters and hydration helpers for retrieval search results."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Sequence
from dataclasses import dataclass

from backend.common.models import RetrievalHit, SectionType


@dataclass(frozen=True)
class RetrievalFilters:
    """Metadata constraints supported by retrieve_evidence."""

    paper_ids: tuple[str, ...] | None = None
    section_types: tuple[SectionType, ...] | None = None
    year_from: int | None = None
    year_to: int | None = None


@dataclass(frozen=True)
class ChunkRecord:
    """Joined chunk + paper metadata needed to build RetrievalHit payloads."""

    chunk_id: str
    paper_id: str
    text: str
    paper_title: str
    authors: str
    year: int | None
    section_type: SectionType | None
    heading: str | None
    page_start: int | None

    def to_hit(
        self,
        *,
        score: float,
        vector_score: float | None = None,
        text_score: float | None = None,
        highlights: list[str] | None = None,
    ) -> RetrievalHit:
        return RetrievalHit(
            chunk_id=self.chunk_id,
            paper_id=self.paper_id,
            text=self.text,
            score=_clamp_score(score),
            vector_score=None if vector_score is None else _clamp_score(vector_score),
            text_score=None if text_score is None else _clamp_score(text_score),
            paper_title=self.paper_title,
            authors=self.authors,
            year=self.year,
            section_type=self.section_type,
            heading=self.heading,
            page_start=self.page_start,
            highlights=highlights,
        )


@dataclass(frozen=True)
class SearchRun:
    """Search results plus a light diagnostic count for tool responses."""

    hits: list[RetrievalHit]
    total_candidates: int


def fetch_chunk_records(
    connection: sqlite3.Connection,
    *,
    filters: RetrievalFilters | None = None,
    chunk_ids: Sequence[str] | None = None,
) -> list[ChunkRecord]:
    """Fetch retrieval-ready chunk metadata from SQLite."""

    resolved_filters = filters or RetrievalFilters()
    where_clauses = ["p.status = ?"]
    parameters: list[object] = ["ready"]

    if chunk_ids is not None:
        materialized_ids = [chunk_id for chunk_id in chunk_ids if chunk_id]
        if not materialized_ids:
            return []
        placeholders = ", ".join("?" for _ in materialized_ids)
        where_clauses.append(f"c.chunk_id IN ({placeholders})")
        parameters.extend(materialized_ids)

    if resolved_filters.paper_ids:
        placeholders = ", ".join("?" for _ in resolved_filters.paper_ids)
        where_clauses.append(f"p.paper_id IN ({placeholders})")
        parameters.extend(resolved_filters.paper_ids)

    if resolved_filters.section_types:
        placeholders = ", ".join("?" for _ in resolved_filters.section_types)
        where_clauses.append(f"c.section_type IN ({placeholders})")
        parameters.extend(resolved_filters.section_types)

    if resolved_filters.year_from is not None:
        where_clauses.append("p.year IS NOT NULL AND p.year >= ?")
        parameters.append(resolved_filters.year_from)

    if resolved_filters.year_to is not None:
        where_clauses.append("p.year IS NOT NULL AND p.year <= ?")
        parameters.append(resolved_filters.year_to)

    rows = connection.execute(
        f"""
        SELECT
            c.chunk_id,
            c.paper_id,
            c.text,
            c.section_type,
            c.heading,
            c.page_start,
            p.title AS paper_title,
            p.authors_json,
            p.year
        FROM chunks AS c
        JOIN papers AS p ON p.paper_id = c.paper_id
        WHERE {" AND ".join(where_clauses)}
        ORDER BY p.year DESC NULLS LAST, c.order_index ASC, c.chunk_id ASC
        """,
        parameters,
    ).fetchall()

    records = [
        ChunkRecord(
            chunk_id=str(row["chunk_id"]),
            paper_id=str(row["paper_id"]),
            text=str(row["text"]),
            paper_title=str(row["paper_title"]),
            authors=_format_authors(str(row["authors_json"])),
            year=None if row["year"] is None else int(row["year"]),
            section_type=row["section_type"],
            heading=row["heading"],
            page_start=None if row["page_start"] is None else int(row["page_start"]),
        )
        for row in rows
    ]

    if chunk_ids is None:
        return records

    order = {chunk_id: index for index, chunk_id in enumerate(chunk_ids)}
    return sorted(records, key=lambda record: order.get(record.chunk_id, len(order)))


def validate_paper_ids(
    connection: sqlite3.Connection,
    paper_ids: Sequence[str] | None,
) -> list[str]:
    """Return any requested paper_ids that do not exist in SQLite."""

    if not paper_ids:
        return []

    materialized_ids = [paper_id for paper_id in paper_ids if paper_id]
    placeholders = ", ".join("?" for _ in materialized_ids)
    rows = connection.execute(
        f"SELECT paper_id FROM papers WHERE paper_id IN ({placeholders})",
        materialized_ids,
    ).fetchall()
    existing = {str(row["paper_id"]) for row in rows}
    return [paper_id for paper_id in materialized_ids if paper_id not in existing]


def count_ready_chunks(
    connection: sqlite3.Connection,
    *,
    filters: RetrievalFilters | None = None,
) -> int:
    """Count ready chunks after applying metadata filters."""

    resolved_filters = filters or RetrievalFilters()
    where_clauses = ["p.status = ?"]
    parameters: list[object] = ["ready"]

    if resolved_filters.paper_ids:
        placeholders = ", ".join("?" for _ in resolved_filters.paper_ids)
        where_clauses.append(f"p.paper_id IN ({placeholders})")
        parameters.extend(resolved_filters.paper_ids)

    if resolved_filters.section_types:
        placeholders = ", ".join("?" for _ in resolved_filters.section_types)
        where_clauses.append(f"c.section_type IN ({placeholders})")
        parameters.extend(resolved_filters.section_types)

    if resolved_filters.year_from is not None:
        where_clauses.append("p.year IS NOT NULL AND p.year >= ?")
        parameters.append(resolved_filters.year_from)

    if resolved_filters.year_to is not None:
        where_clauses.append("p.year IS NOT NULL AND p.year <= ?")
        parameters.append(resolved_filters.year_to)

    row = connection.execute(
        f"""
        SELECT COUNT(*) AS chunk_count
        FROM chunks AS c
        JOIN papers AS p ON p.paper_id = c.paper_id
        WHERE {" AND ".join(where_clauses)}
        """,
        parameters,
    ).fetchone()
    return 0 if row is None else int(row["chunk_count"])


def _format_authors(authors_json: str) -> str:
    payload = json.loads(authors_json or "[]")
    if not isinstance(payload, list):
        return ""

    names = [
        str(author.get("name", "")).strip()
        for author in payload
        if isinstance(author, dict) and str(author.get("name", "")).strip()
    ]
    return ", ".join(names)


def _clamp_score(score: float) -> float:
    return max(0.0, min(1.0, float(score)))
