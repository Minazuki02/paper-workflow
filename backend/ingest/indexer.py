"""Persistence coordinator for Phase 1 ingest indexing."""

from __future__ import annotations

import sqlite3
from collections.abc import Sequence
from dataclasses import dataclass

from backend.common.errors import DB_WRITE_FAILED, INDEX_WRITE_FAILED
from backend.common.models import Chunk, Paper, Section
from backend.storage.faiss_store import FaissStore
from backend.storage.sqlite_store import SQLiteMetadataStore


class IndexerError(RuntimeError):
    """Raised when metadata or vector index persistence fails."""

    def __init__(self, error_code: str, message: str) -> None:
        super().__init__(message)
        self.error_code = error_code


@dataclass(frozen=True)
class IndexWriteResult:
    """Summary of a successful metadata + vector write."""

    paper_id: str
    section_count: int
    chunk_count: int
    vector_count: int


@dataclass(frozen=True)
class _PaperSnapshot:
    paper: Paper | None
    sections: list[Section]
    chunks: list[Chunk]


class PaperIndexer:
    """Write structured ingest output to SQLite and FAISS without owning orchestration."""

    def __init__(
        self,
        metadata_store: SQLiteMetadataStore,
        vector_store: FaissStore,
    ) -> None:
        self._metadata_store = metadata_store
        self._vector_store = vector_store

    def index_paper(
        self,
        paper: Paper,
        sections: Sequence[Section],
        chunks: Sequence[Chunk],
        embeddings: Sequence[Sequence[float]],
        *,
        replace_existing: bool = False,
    ) -> IndexWriteResult:
        """Persist one paper's structured data and aligned chunk vectors."""

        materialized_sections = list(sections)
        materialized_chunks = list(chunks)
        materialized_embeddings = self._validate_inputs(
            paper=paper,
            sections=materialized_sections,
            chunks=materialized_chunks,
            embeddings=embeddings,
        )

        existing_chunks = self._metadata_store.get_chunks(paper.paper_id)
        if existing_chunks and not replace_existing:
            raise IndexerError(
                INDEX_WRITE_FAILED,
                f"Paper '{paper.paper_id}' already has indexed chunks; reindex is out of scope.",
            )

        snapshot = self._snapshot(paper.paper_id)
        self._vector_store.load()
        if existing_chunks and replace_existing:
            self._vector_store.remove([chunk.chunk_id for chunk in existing_chunks])
        persisted_paper = paper.model_copy(
            update={
                "section_count": len(materialized_sections),
                "chunk_count": len(materialized_chunks),
            }
        )

        try:
            self._metadata_store.upsert_paper(persisted_paper)
            stored_sections = self._metadata_store.replace_sections(paper.paper_id, materialized_sections)
            stored_chunks = self._metadata_store.replace_chunks(paper.paper_id, materialized_chunks)
        except sqlite3.Error as exc:
            self._restore_snapshot(snapshot, paper_id=paper.paper_id)
            raise IndexerError(
                DB_WRITE_FAILED,
                f"Failed to persist metadata for paper '{paper.paper_id}'.",
            ) from exc

        if stored_chunks:
            try:
                self._maybe_recreate_empty_index_for_new_dimension(
                    existing_chunks=existing_chunks,
                    replace_existing=replace_existing,
                    embeddings=materialized_embeddings,
                )
                self._vector_store.add(
                    [chunk.chunk_id for chunk in stored_chunks],
                    materialized_embeddings,
                )
                self._vector_store.save()
            except Exception as exc:
                self._restore_snapshot(snapshot, paper_id=paper.paper_id)
                self._vector_store.load()
                raise IndexerError(
                    INDEX_WRITE_FAILED,
                    f"Failed to persist vectors for paper '{paper.paper_id}'.",
                ) from exc

        final_paper = self._metadata_store.get_paper(paper.paper_id)
        if final_paper is None:
            raise RuntimeError(f"Paper '{paper.paper_id}' disappeared after indexing.")

        return IndexWriteResult(
            paper_id=final_paper.paper_id,
            section_count=final_paper.section_count,
            chunk_count=final_paper.chunk_count,
            vector_count=len(stored_chunks),
        )

    def _validate_inputs(
        self,
        *,
        paper: Paper,
        sections: Sequence[Section],
        chunks: Sequence[Chunk],
        embeddings: Sequence[Sequence[float]],
    ) -> list[list[float]]:
        if len(chunks) != len(embeddings):
            raise ValueError("Chunk count must match embedding count.")

        if any(section.paper_id != paper.paper_id for section in sections):
            raise ValueError("All sections must belong to the indexed paper.")
        if any(chunk.paper_id != paper.paper_id for chunk in chunks):
            raise ValueError("All chunks must belong to the indexed paper.")

        materialized_embeddings = [[float(value) for value in embedding] for embedding in embeddings]
        if any(len(vector) == 0 for vector in materialized_embeddings):
            raise ValueError("Embeddings must not contain empty vectors.")

        dimensions = {len(vector) for vector in materialized_embeddings}
        if len(dimensions) > 1:
            raise ValueError("All embeddings must share the same dimension.")

        return materialized_embeddings

    def _maybe_recreate_empty_index_for_new_dimension(
        self,
        *,
        existing_chunks: Sequence[Chunk],
        replace_existing: bool,
        embeddings: Sequence[Sequence[float]],
    ) -> None:
        if not existing_chunks or not replace_existing or not embeddings:
            return
        if getattr(self._vector_store, "size", 0) != 0:
            return

        current_dimension = getattr(self._vector_store, "dimension", None)
        target_dimension = len(embeddings[0])
        if current_dimension in {None, target_dimension}:
            return

        self._vector_store.create(target_dimension, metric=getattr(self._vector_store, "metric", "cosine"))

    def _snapshot(self, paper_id: str) -> _PaperSnapshot:
        return _PaperSnapshot(
            paper=self._metadata_store.get_paper(paper_id),
            sections=self._metadata_store.get_sections(paper_id),
            chunks=self._metadata_store.get_chunks(paper_id),
        )

    def _restore_snapshot(self, snapshot: _PaperSnapshot, *, paper_id: str) -> None:
        if snapshot.paper is None:
            with self._metadata_store.connection:
                self._metadata_store.connection.execute(
                    "DELETE FROM papers WHERE paper_id = ?",
                    (paper_id,),
                )
            return

        self._metadata_store.upsert_paper(snapshot.paper)
        self._metadata_store.replace_sections(paper_id, snapshot.sections)
        self._metadata_store.replace_chunks(paper_id, snapshot.chunks)
