"""SQLite FTS5-backed keyword retrieval for chunk evidence search."""

from __future__ import annotations

import re

from backend.retrieval.filters import RetrievalFilters, SearchRun, fetch_chunk_records
from backend.storage.sqlite_store import SQLiteMetadataStore

_FTS_TABLE = "retrieval_chunks_fts"
_TOKEN_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]*")


class TextSearcher:
    """Run lightweight full-text retrieval using a temp FTS5 table."""

    def __init__(self, *, metadata_store: SQLiteMetadataStore | None = None) -> None:
        self._metadata_store = metadata_store or SQLiteMetadataStore()

    def search(
        self,
        query: str,
        *,
        top_k: int = 10,
        filters: RetrievalFilters | None = None,
        min_score: float = 0.0,
    ) -> SearchRun:
        """Search chunk text with SQLite FTS5 and return RetrievalHit rows."""

        if top_k <= 0:
            return SearchRun(hits=[], total_candidates=0)

        connection = self._metadata_store.connection
        records = fetch_chunk_records(connection, filters=filters)
        if not records:
            return SearchRun(hits=[], total_candidates=0)

        self._refresh_fts_index(records)
        match_query = _build_match_query(query)
        if not match_query:
            return SearchRun(hits=[], total_candidates=0)

        candidate_limit = max(top_k * 5, top_k, 25)
        rows = connection.execute(
            f"""
            SELECT
                chunk_id,
                bm25({_FTS_TABLE}) AS bm25_score,
                snippet({_FTS_TABLE}, 8, '[', ']', ' ... ', 18) AS snippet_text
            FROM {_FTS_TABLE}
            WHERE {_FTS_TABLE} MATCH ?
            ORDER BY bm25_score ASC, chunk_id ASC
            LIMIT ?
            """,
            (match_query, candidate_limit),
        ).fetchall()

        if not rows:
            return SearchRun(hits=[], total_candidates=0)

        record_map = {record.chunk_id: record for record in records}
        candidates = []
        for rank, row in enumerate(rows, start=1):
            record = record_map.get(str(row["chunk_id"]))
            if record is None:
                continue
            text_score = _rank_to_score(rank)
            snippet = _normalize_snippet(row["snippet_text"])
            candidates.append(
                record.to_hit(
                    score=text_score,
                    text_score=text_score,
                    highlights=None if snippet is None else [snippet],
                )
            )

        final_hits = [hit for hit in candidates if hit.score >= min_score][:top_k]
        return SearchRun(hits=final_hits, total_candidates=len(candidates))

    def _refresh_fts_index(self, records) -> None:
        connection = self._metadata_store.connection
        connection.execute(
            f"""
            CREATE VIRTUAL TABLE IF NOT EXISTS temp.{_FTS_TABLE}
            USING fts5(
                chunk_id UNINDEXED,
                paper_id UNINDEXED,
                paper_title UNINDEXED,
                authors UNINDEXED,
                year UNINDEXED,
                section_type UNINDEXED,
                heading UNINDEXED,
                page_start UNINDEXED,
                text
            )
            """
        )
        with connection:
            connection.execute(f"DELETE FROM {_FTS_TABLE}")
            connection.executemany(
                f"""
                INSERT INTO {_FTS_TABLE} (
                    chunk_id,
                    paper_id,
                    paper_title,
                    authors,
                    year,
                    section_type,
                    heading,
                    page_start,
                    text
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        record.chunk_id,
                        record.paper_id,
                        record.paper_title,
                        record.authors,
                        "" if record.year is None else str(record.year),
                        record.section_type,
                        record.heading,
                        None if record.page_start is None else str(record.page_start),
                        record.text,
                    )
                    for record in records
                ],
            )


def _build_match_query(query: str) -> str:
    tokens = _TOKEN_RE.findall(query)
    if not tokens:
        cleaned = query.strip().replace('"', '""')
        return f'"{cleaned}"' if cleaned else ""
    return " OR ".join(f'"{token}"' for token in tokens)


def _rank_to_score(rank: int) -> float:
    return 1.0 / float(rank)


def _normalize_snippet(snippet: str | None) -> str | None:
    if snippet is None:
        return None
    cleaned = str(snippet).strip()
    return cleaned or None
