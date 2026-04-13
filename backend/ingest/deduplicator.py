"""Duplicate detection helpers for Phase 1 ingest."""

from __future__ import annotations

import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Literal

from backend.common.models import Paper
from backend.storage.sqlite_store import SQLiteMetadataStore

MatchType = Literal["doi", "title"]

_TITLE_NORMALIZE_PATTERN = re.compile(r"[\W_]+", re.UNICODE)


@dataclass(frozen=True)
class DeduplicationResult:
    """Describe whether an incoming paper collides with an existing paper."""

    is_duplicate: bool
    existing_paper_id: str | None = None
    match_type: MatchType | None = None
    similarity: float | None = None
    existing_title: str | None = None


class PaperDeduplicator:
    """Detect exact DOI matches and high-similarity title matches."""

    def __init__(
        self,
        store: SQLiteMetadataStore,
        *,
        title_similarity_threshold: float = 0.92,
    ) -> None:
        self._store = store
        self._title_similarity_threshold = title_similarity_threshold

    def find_duplicate(self, paper: Paper) -> DeduplicationResult:
        """Return a stable duplicate decision without mutating ingest state."""

        doi_match = self._find_duplicate_by_doi(paper)
        if doi_match is not None:
            return doi_match

        title_match = self._find_duplicate_by_title(paper)
        if title_match is not None:
            return title_match

        return DeduplicationResult(is_duplicate=False)

    def _find_duplicate_by_doi(self, paper: Paper) -> DeduplicationResult | None:
        normalized_doi = _normalize_doi(paper.doi)
        if normalized_doi is None:
            return None

        row = self._store.connection.execute(
            """
            SELECT paper_id, title
            FROM papers
            WHERE LOWER(TRIM(doi)) = ?
            LIMIT 1
            """,
            (normalized_doi,),
        ).fetchone()
        if row is None:
            return None

        return DeduplicationResult(
            is_duplicate=True,
            existing_paper_id=str(row["paper_id"]),
            match_type="doi",
            similarity=1.0,
            existing_title=str(row["title"]),
        )

    def _find_duplicate_by_title(self, paper: Paper) -> DeduplicationResult | None:
        normalized_title = _normalize_title(paper.title)
        if not normalized_title:
            return None

        best_match: DeduplicationResult | None = None
        rows = self._store.connection.execute(
            "SELECT paper_id, title FROM papers WHERE title IS NOT NULL AND title != ''"
        ).fetchall()

        for row in rows:
            existing_title = str(row["title"])
            similarity = SequenceMatcher(
                None,
                normalized_title,
                _normalize_title(existing_title),
            ).ratio()

            if similarity < self._title_similarity_threshold:
                continue

            if best_match is None or similarity > (best_match.similarity or 0.0):
                best_match = DeduplicationResult(
                    is_duplicate=True,
                    existing_paper_id=str(row["paper_id"]),
                    match_type="title",
                    similarity=similarity,
                    existing_title=existing_title,
                )

        return best_match


def _normalize_doi(doi: str | None) -> str | None:
    if doi is None:
        return None
    cleaned = doi.strip().lower()
    return cleaned or None


def _normalize_title(title: str) -> str:
    collapsed = _TITLE_NORMALIZE_PATTERN.sub(" ", title.casefold())
    return " ".join(collapsed.split())
