"""Shared Pydantic models for the paper workflow backend."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


def _uuid4_str() -> str:
    """Return a UUID v4 string for backend entity identifiers."""

    return str(uuid4())


def _utc_now_iso() -> str:
    """Return an ISO 8601 UTC timestamp with a trailing Z."""

    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


PaperStatus = Literal[
    "discovered",
    "queued",
    "downloading",
    "downloaded",
    "parsing",
    "parsed",
    "chunked",
    "embedding",
    "indexed",
    "ready",
    "failed",
    "archived",
]

JobStatus = Literal["pending", "running", "completed", "partial", "failed", "cancelled"]

SectionType = Literal[
    "abstract",
    "introduction",
    "related_work",
    "methodology",
    "experiments",
    "discussion",
    "conclusion",
    "appendix",
    "references",
    "other",
]

AnalysisTaskType = Literal[
    "single_paper",
    "comparison",
    "evidence_extraction",
    "synthesis",
    "trend",
]


class BackendModel(BaseModel):
    """Base model used by shared backend contracts."""

    model_config = ConfigDict(extra="forbid")


class Author(BackendModel):
    name: str
    affiliation: str | None = None
    email: str | None = None


class Paper(BackendModel):
    paper_id: str = Field(default_factory=_uuid4_str)
    doi: str | None = None
    arxiv_id: str | None = None
    semantic_scholar_id: str | None = None
    title: str
    authors: list[Author] = Field(default_factory=list)
    abstract: str = ""
    year: int | None = None
    venue: str | None = None
    keywords: list[str] = Field(default_factory=list)
    url: str | None = None
    pdf_url: str | None = None
    status: PaperStatus = "discovered"
    ingested_at: str | None = None
    updated_at: str = Field(default_factory=_utc_now_iso)
    pdf_path: str | None = None
    pdf_hash: str | None = None
    chunk_count: int = 0
    section_count: int = 0
    citation_count: int | None = None


class Section(BackendModel):
    section_id: str = Field(default_factory=_uuid4_str)
    paper_id: str
    heading: str
    section_type: SectionType
    level: int
    order_index: int
    text: str
    char_count: int
    parent_id: str | None = None


class Chunk(BackendModel):
    chunk_id: str = Field(default_factory=_uuid4_str)
    paper_id: str
    section_id: str | None = None
    text: str
    char_count: int
    token_count: int | None = None
    order_index: int
    page_start: int | None = None
    page_end: int | None = None
    embedding_model: str | None = None
    section_type: SectionType | None = None
    heading: str | None = None


class IngestError(BackendModel):
    url: str
    stage: PaperStatus
    error_code: str
    error_message: str
    retryable: bool


class IngestOptions(BackendModel):
    skip_existing: bool = True
    force_reparse: bool = False
    max_retries: int = 3
    parser: Literal["pymupdf", "grobid"] = "pymupdf"


class IngestJob(BackendModel):
    job_id: str = Field(default_factory=_uuid4_str)
    job_type: Literal["single", "batch"]
    status: JobStatus = "pending"
    created_at: str = Field(default_factory=_utc_now_iso)
    started_at: str | None = None
    completed_at: str | None = None
    paper_urls: list[str] = Field(default_factory=list)
    total_count: int
    succeeded: int = 0
    failed: int = 0
    skipped: int = 0
    in_progress: int = 0
    paper_ids: list[str] = Field(default_factory=list)
    errors: list[IngestError] = Field(default_factory=list)
    options: IngestOptions | None = None


class RetrievalHit(BackendModel):
    chunk_id: str
    paper_id: str
    text: str
    score: float
    vector_score: float | None = None
    text_score: float | None = None
    paper_title: str
    authors: str
    year: int | None = None
    section_type: SectionType | None = None
    heading: str | None = None
    page_start: int | None = None
    highlights: list[str] | None = None


class Evidence(BackendModel):
    evidence_id: str = Field(default_factory=_uuid4_str)
    claim: str
    text: str
    chunk_id: str
    paper_id: str
    paper_title: str
    section_type: SectionType | None = None
    confidence: float
    evidence_type: Literal[
        "quantitative",
        "qualitative",
        "methodological",
        "theoretical",
    ] | None = None
    page: int | None = None


class AnalysisTask(BackendModel):
    task_id: str = Field(default_factory=_uuid4_str)
    task_type: AnalysisTaskType
    status: JobStatus = "pending"
    created_at: str = Field(default_factory=_utc_now_iso)
    completed_at: str | None = None
    paper_ids: list[str] = Field(default_factory=list)
    focus: str | None = None
    user_query: str | None = None
    result_id: str | None = None
    error: str | None = None


class AnalysisResult(BackendModel):
    result_id: str = Field(default_factory=_uuid4_str)
    task_id: str
    paper_id: str
    summary: str
    contributions: list[str] = Field(default_factory=list)
    methodology: str
    key_findings: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    future_work: list[str] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)
    model_used: str
    generated_at: str = Field(default_factory=_utc_now_iso)
    token_cost: int | None = None


class ToolError(BackendModel):
    error: Literal[True] = True
    error_code: str
    error_message: str
    retryable: bool
    details: dict[str, Any] | None = None

