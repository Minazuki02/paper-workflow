"""SQLite-backed metadata persistence for Phase 1 entities."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterable

from backend.common.db import initialize_database
from backend.common.models import Chunk, IngestError, IngestJob, IngestOptions, Paper, Section


class SQLiteMetadataStore:
    """Persist Paper workflow metadata without adding ORM complexity."""

    def __init__(self, connection: sqlite3.Connection | None = None) -> None:
        self._connection = connection or initialize_database()

    @property
    def connection(self) -> sqlite3.Connection:
        return self._connection

    def upsert_paper(self, paper: Paper) -> Paper:
        payload = paper.model_dump()
        with self._connection:
            self._connection.execute(
                """
                INSERT INTO papers (
                    paper_id,
                    doi,
                    arxiv_id,
                    semantic_scholar_id,
                    title,
                    authors_json,
                    abstract,
                    year,
                    venue,
                    keywords_json,
                    url,
                    pdf_url,
                    status,
                    ingested_at,
                    updated_at,
                    pdf_path,
                    pdf_hash,
                    chunk_count,
                    section_count,
                    citation_count
                ) VALUES (
                    :paper_id,
                    :doi,
                    :arxiv_id,
                    :semantic_scholar_id,
                    :title,
                    :authors_json,
                    :abstract,
                    :year,
                    :venue,
                    :keywords_json,
                    :url,
                    :pdf_url,
                    :status,
                    :ingested_at,
                    :updated_at,
                    :pdf_path,
                    :pdf_hash,
                    :chunk_count,
                    :section_count,
                    :citation_count
                )
                ON CONFLICT(paper_id) DO UPDATE SET
                    doi = excluded.doi,
                    arxiv_id = excluded.arxiv_id,
                    semantic_scholar_id = excluded.semantic_scholar_id,
                    title = excluded.title,
                    authors_json = excluded.authors_json,
                    abstract = excluded.abstract,
                    year = excluded.year,
                    venue = excluded.venue,
                    keywords_json = excluded.keywords_json,
                    url = excluded.url,
                    pdf_url = excluded.pdf_url,
                    status = excluded.status,
                    ingested_at = excluded.ingested_at,
                    updated_at = excluded.updated_at,
                    pdf_path = excluded.pdf_path,
                    pdf_hash = excluded.pdf_hash,
                    chunk_count = excluded.chunk_count,
                    section_count = excluded.section_count,
                    citation_count = excluded.citation_count
                """,
                self._paper_params(payload),
            )

        stored = self.get_paper(paper.paper_id)
        if stored is None:
            raise LookupError(f"Paper was not persisted: {paper.paper_id}")
        return stored

    def get_paper(self, paper_id: str) -> Paper | None:
        row = self._connection.execute(
            "SELECT * FROM papers WHERE paper_id = ?",
            (paper_id,),
        ).fetchone()
        return None if row is None else self._paper_from_row(row)

    def list_papers(self, *, limit: int = 100, offset: int = 0) -> list[Paper]:
        rows = self._connection.execute(
            """
            SELECT *
            FROM papers
            ORDER BY updated_at DESC, paper_id ASC
            LIMIT ? OFFSET ?
            """,
            (limit, offset),
        ).fetchall()
        return [self._paper_from_row(row) for row in rows]

    def replace_sections(self, paper_id: str, sections: Iterable[Section]) -> list[Section]:
        materialized = list(sections)

        with self._connection:
            self._connection.execute("DELETE FROM sections WHERE paper_id = ?", (paper_id,))
            if materialized:
                self._connection.executemany(
                    """
                    INSERT INTO sections (
                        section_id,
                        paper_id,
                        heading,
                        section_type,
                        level,
                        order_index,
                        text,
                        char_count,
                        parent_id
                    ) VALUES (
                        :section_id,
                        :paper_id,
                        :heading,
                        :section_type,
                        :level,
                        :order_index,
                        :text,
                        :char_count,
                        :parent_id
                    )
                    """,
                    [section.model_dump() for section in materialized],
                )
            self._update_paper_count(paper_id, column="section_count", count=len(materialized))

        return self.get_sections(paper_id)

    def get_sections(self, paper_id: str) -> list[Section]:
        rows = self._connection.execute(
            """
            SELECT *
            FROM sections
            WHERE paper_id = ?
            ORDER BY order_index ASC, section_id ASC
            """,
            (paper_id,),
        ).fetchall()
        return [Section.model_validate(dict(row)) for row in rows]

    def replace_chunks(self, paper_id: str, chunks: Iterable[Chunk]) -> list[Chunk]:
        materialized = list(chunks)

        with self._connection:
            self._connection.execute("DELETE FROM chunks WHERE paper_id = ?", (paper_id,))
            if materialized:
                self._connection.executemany(
                    """
                    INSERT INTO chunks (
                        chunk_id,
                        paper_id,
                        section_id,
                        text,
                        char_count,
                        token_count,
                        order_index,
                        page_start,
                        page_end,
                        embedding_model,
                        section_type,
                        heading
                    ) VALUES (
                        :chunk_id,
                        :paper_id,
                        :section_id,
                        :text,
                        :char_count,
                        :token_count,
                        :order_index,
                        :page_start,
                        :page_end,
                        :embedding_model,
                        :section_type,
                        :heading
                    )
                    """,
                    [chunk.model_dump() for chunk in materialized],
                )
            self._update_paper_count(paper_id, column="chunk_count", count=len(materialized))

        return self.get_chunks(paper_id)

    def get_chunks(self, paper_id: str) -> list[Chunk]:
        rows = self._connection.execute(
            """
            SELECT *
            FROM chunks
            WHERE paper_id = ?
            ORDER BY order_index ASC, chunk_id ASC
            """,
            (paper_id,),
        ).fetchall()
        return [Chunk.model_validate(dict(row)) for row in rows]

    def upsert_ingest_job(self, job: IngestJob) -> IngestJob:
        payload = job.model_dump()
        with self._connection:
            self._connection.execute(
                """
                INSERT INTO ingest_jobs (
                    job_id,
                    job_type,
                    status,
                    created_at,
                    started_at,
                    completed_at,
                    paper_urls_json,
                    total_count,
                    succeeded,
                    failed,
                    skipped,
                    in_progress,
                    paper_ids_json,
                    errors_json,
                    options_json
                ) VALUES (
                    :job_id,
                    :job_type,
                    :status,
                    :created_at,
                    :started_at,
                    :completed_at,
                    :paper_urls_json,
                    :total_count,
                    :succeeded,
                    :failed,
                    :skipped,
                    :in_progress,
                    :paper_ids_json,
                    :errors_json,
                    :options_json
                )
                ON CONFLICT(job_id) DO UPDATE SET
                    job_type = excluded.job_type,
                    status = excluded.status,
                    created_at = excluded.created_at,
                    started_at = excluded.started_at,
                    completed_at = excluded.completed_at,
                    paper_urls_json = excluded.paper_urls_json,
                    total_count = excluded.total_count,
                    succeeded = excluded.succeeded,
                    failed = excluded.failed,
                    skipped = excluded.skipped,
                    in_progress = excluded.in_progress,
                    paper_ids_json = excluded.paper_ids_json,
                    errors_json = excluded.errors_json,
                    options_json = excluded.options_json
                """,
                self._ingest_job_params(payload),
            )

        stored = self.get_ingest_job(job.job_id)
        if stored is None:
            raise LookupError(f"Ingest job was not persisted: {job.job_id}")
        return stored

    def get_ingest_job(self, job_id: str) -> IngestJob | None:
        row = self._connection.execute(
            "SELECT * FROM ingest_jobs WHERE job_id = ?",
            (job_id,),
        ).fetchone()
        return None if row is None else self._ingest_job_from_row(row)

    def list_ingest_jobs(self, *, limit: int = 100, offset: int = 0) -> list[IngestJob]:
        rows = self._connection.execute(
            """
            SELECT *
            FROM ingest_jobs
            ORDER BY created_at DESC, job_id ASC
            LIMIT ? OFFSET ?
            """,
            (limit, offset),
        ).fetchall()
        return [self._ingest_job_from_row(row) for row in rows]

    def _update_paper_count(self, paper_id: str, *, column: str, count: int) -> None:
        if column not in {"section_count", "chunk_count"}:
            raise ValueError(f"Unsupported paper counter column: {column}")

        self._connection.execute(
            f"UPDATE papers SET {column} = ? WHERE paper_id = ?",
            (count, paper_id),
        )

    def _paper_from_row(self, row: sqlite3.Row) -> Paper:
        payload = dict(row)
        payload["authors"] = json.loads(payload.pop("authors_json"))
        payload["keywords"] = json.loads(payload.pop("keywords_json"))
        return Paper.model_validate(payload)

    def _paper_params(self, payload: dict[str, object]) -> dict[str, object]:
        encoded = dict(payload)
        encoded["authors_json"] = json.dumps(encoded.pop("authors"))
        encoded["keywords_json"] = json.dumps(encoded.pop("keywords"))
        return encoded

    def _ingest_job_from_row(self, row: sqlite3.Row) -> IngestJob:
        payload = dict(row)
        payload["paper_urls"] = json.loads(payload.pop("paper_urls_json"))
        payload["paper_ids"] = json.loads(payload.pop("paper_ids_json"))
        payload["errors"] = [
            IngestError.model_validate(item) for item in json.loads(payload.pop("errors_json"))
        ]

        options_json = payload.pop("options_json")
        payload["options"] = None if options_json is None else IngestOptions.model_validate(
            json.loads(options_json)
        )
        return IngestJob.model_validate(payload)

    def _ingest_job_params(self, payload: dict[str, object]) -> dict[str, object]:
        encoded = dict(payload)
        encoded["paper_urls_json"] = json.dumps(encoded.pop("paper_urls"))
        encoded["paper_ids_json"] = json.dumps(encoded.pop("paper_ids"))
        encoded["errors_json"] = json.dumps(encoded.pop("errors"))

        options = encoded.pop("options")
        encoded["options_json"] = None if options is None else json.dumps(options)
        return encoded
