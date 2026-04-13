"""SQLite initialization and minimal migration helpers."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import get_args

from backend.common.config import AppConfig, load_settings
from backend.common.models import JobStatus, PaperStatus, SectionType


@dataclass(frozen=True)
class Migration:
    version: int
    name: str
    script: str


def _sql_tuple(values: tuple[str, ...]) -> str:
    return ", ".join("'" + value.replace("'", "''") + "'" for value in values)


SCHEMA_MIGRATIONS_TABLE = "schema_migrations"
_PAPER_STATUS_SQL = _sql_tuple(get_args(PaperStatus))
_JOB_STATUS_SQL = _sql_tuple(get_args(JobStatus))
_SECTION_TYPE_SQL = _sql_tuple(get_args(SectionType))

MIGRATIONS: tuple[Migration, ...] = (
    Migration(
        version=1,
        name="phase1_foundation",
        script=f"""
        CREATE TABLE IF NOT EXISTS papers (
            paper_id TEXT PRIMARY KEY,
            doi TEXT,
            arxiv_id TEXT,
            semantic_scholar_id TEXT,
            title TEXT NOT NULL,
            authors_json TEXT NOT NULL,
            abstract TEXT NOT NULL DEFAULT '',
            year INTEGER,
            venue TEXT,
            keywords_json TEXT NOT NULL DEFAULT '[]',
            url TEXT,
            pdf_url TEXT,
            status TEXT NOT NULL CHECK (status IN ({_PAPER_STATUS_SQL})),
            ingested_at TEXT,
            updated_at TEXT NOT NULL,
            pdf_path TEXT,
            pdf_hash TEXT,
            chunk_count INTEGER NOT NULL DEFAULT 0,
            section_count INTEGER NOT NULL DEFAULT 0,
            citation_count INTEGER
        );

        CREATE INDEX IF NOT EXISTS idx_papers_status ON papers(status);
        CREATE INDEX IF NOT EXISTS idx_papers_doi ON papers(doi);
        CREATE INDEX IF NOT EXISTS idx_papers_arxiv_id ON papers(arxiv_id);
        CREATE INDEX IF NOT EXISTS idx_papers_pdf_hash ON papers(pdf_hash);

        CREATE TABLE IF NOT EXISTS sections (
            section_id TEXT PRIMARY KEY,
            paper_id TEXT NOT NULL,
            heading TEXT NOT NULL,
            section_type TEXT NOT NULL CHECK (section_type IN ({_SECTION_TYPE_SQL})),
            level INTEGER NOT NULL,
            order_index INTEGER NOT NULL,
            text TEXT NOT NULL,
            char_count INTEGER NOT NULL,
            parent_id TEXT,
            FOREIGN KEY (paper_id) REFERENCES papers(paper_id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_sections_paper_order
            ON sections(paper_id, order_index);

        CREATE TABLE IF NOT EXISTS chunks (
            chunk_id TEXT PRIMARY KEY,
            paper_id TEXT NOT NULL,
            section_id TEXT,
            text TEXT NOT NULL,
            char_count INTEGER NOT NULL,
            token_count INTEGER,
            order_index INTEGER NOT NULL,
            page_start INTEGER,
            page_end INTEGER,
            embedding_model TEXT,
            section_type TEXT CHECK (section_type IS NULL OR section_type IN ({_SECTION_TYPE_SQL})),
            heading TEXT,
            FOREIGN KEY (paper_id) REFERENCES papers(paper_id) ON DELETE CASCADE,
            FOREIGN KEY (section_id) REFERENCES sections(section_id) ON DELETE SET NULL
        );

        CREATE INDEX IF NOT EXISTS idx_chunks_paper_order
            ON chunks(paper_id, order_index);
        CREATE INDEX IF NOT EXISTS idx_chunks_section
            ON chunks(section_id);

        CREATE TABLE IF NOT EXISTS ingest_jobs (
            job_id TEXT PRIMARY KEY,
            job_type TEXT NOT NULL CHECK (job_type IN ('single', 'batch')),
            status TEXT NOT NULL CHECK (status IN ({_JOB_STATUS_SQL})),
            created_at TEXT NOT NULL,
            started_at TEXT,
            completed_at TEXT,
            paper_urls_json TEXT NOT NULL,
            total_count INTEGER NOT NULL,
            succeeded INTEGER NOT NULL DEFAULT 0,
            failed INTEGER NOT NULL DEFAULT 0,
            skipped INTEGER NOT NULL DEFAULT 0,
            in_progress INTEGER NOT NULL DEFAULT 0,
            paper_ids_json TEXT NOT NULL DEFAULT '[]',
            errors_json TEXT NOT NULL DEFAULT '[]',
            options_json TEXT,
            CHECK (total_count >= 0),
            CHECK (succeeded >= 0),
            CHECK (failed >= 0),
            CHECK (skipped >= 0),
            CHECK (in_progress >= 0)
        );

        CREATE INDEX IF NOT EXISTS idx_ingest_jobs_status
            ON ingest_jobs(status, created_at);

        CREATE TABLE IF NOT EXISTS parse_metrics (
            paper_id TEXT PRIMARY KEY,
            parser_used TEXT NOT NULL CHECK (parser_used IN ('pymupdf', 'grobid')),
            page_count INTEGER NOT NULL,
            extracted_char_count INTEGER NOT NULL,
            chars_per_page REAL NOT NULL,
            section_count INTEGER NOT NULL DEFAULT 0,
            has_abstract INTEGER NOT NULL DEFAULT 0,
            has_references INTEGER NOT NULL DEFAULT 0,
            reference_count INTEGER NOT NULL DEFAULT 0,
            figure_count INTEGER NOT NULL DEFAULT 0,
            table_count INTEGER NOT NULL DEFAULT 0,
            encoding_issues INTEGER NOT NULL DEFAULT 0,
            confidence REAL,
            recorded_at TEXT NOT NULL,
            FOREIGN KEY (paper_id) REFERENCES papers(paper_id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS paper_traces (
            trace_id INTEGER PRIMARY KEY AUTOINCREMENT,
            paper_id TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            stage TEXT NOT NULL CHECK (stage IN ({_PAPER_STATUS_SQL})),
            event TEXT NOT NULL,
            duration_ms INTEGER,
            metadata_json TEXT NOT NULL DEFAULT '{{}}',
            FOREIGN KEY (paper_id) REFERENCES papers(paper_id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_paper_traces_paper_time
            ON paper_traces(paper_id, timestamp);
        """.strip(),
    ),
)


def initialize_database(
    settings: AppConfig | None = None,
    *,
    db_path: str | Path | None = None,
) -> sqlite3.Connection:
    """Initialize the SQLite database and apply all pending migrations."""

    connection = connect_sqlite(settings, db_path=db_path)
    _ensure_migrations_table(connection)
    _apply_pending_migrations(connection)
    return connection


def connect_sqlite(
    settings: AppConfig | None = None,
    *,
    db_path: str | Path | None = None,
) -> sqlite3.Connection:
    """Create a SQLite connection with the backend defaults enabled."""

    config = settings or load_settings()
    database_target = _resolve_database_target(config, db_path)

    if database_target != ":memory:":
        Path(database_target).parent.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(database_target)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON;")
    connection.execute("PRAGMA journal_mode = WAL;")
    connection.execute("PRAGMA synchronous = NORMAL;")
    return connection


def get_schema_version(connection: sqlite3.Connection) -> int:
    """Return the current schema version stored in SQLite."""

    row = connection.execute("PRAGMA user_version;").fetchone()
    return int(row[0]) if row is not None else 0


def list_tables(connection: sqlite3.Connection) -> list[str]:
    """Return the user-defined tables in the current database."""

    rows = connection.execute(
        """
        SELECT name
        FROM sqlite_master
        WHERE type = 'table' AND name NOT LIKE 'sqlite_%'
        ORDER BY name
        """
    ).fetchall()
    return [str(row["name"]) for row in rows]


def _ensure_migrations_table(connection: sqlite3.Connection) -> None:
    connection.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {SCHEMA_MIGRATIONS_TABLE} (
            version INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            applied_at TEXT NOT NULL
        )
        """
    )
    connection.commit()


def _apply_pending_migrations(connection: sqlite3.Connection) -> None:
    applied_versions = {
        int(row["version"])
        for row in connection.execute(
            f"SELECT version FROM {SCHEMA_MIGRATIONS_TABLE} ORDER BY version"
        ).fetchall()
    }

    for migration in MIGRATIONS:
        if migration.version in applied_versions:
            continue

        with connection:
            connection.executescript(migration.script)
            connection.execute(
                f"""
                INSERT INTO {SCHEMA_MIGRATIONS_TABLE} (version, name, applied_at)
                VALUES (?, ?, ?)
                """,
                (migration.version, migration.name, _utc_now_iso()),
            )
            connection.execute(f"PRAGMA user_version = {migration.version};")


def _resolve_database_target(
    settings: AppConfig,
    db_path: str | Path | None,
) -> str:
    if db_path == ":memory:":
        return ":memory:"

    if db_path is None:
        return str(settings.paths.db_path)

    return str(Path(db_path).expanduser().resolve())


def _utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
