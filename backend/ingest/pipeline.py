"""Single-paper ingest pipeline for the Phase 1 backend."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from backend.common.config import AppConfig, load_settings
from backend.common.errors import (
    DEDUP_CONFLICT,
    SYSTEM_INTERNAL_ERROR,
    is_retryable_error,
)
from backend.common.logging_config import configure_logging, get_logger
from backend.common.models import IngestError, IngestJob, IngestOptions, Paper, PaperStatus, Section
from backend.ingest.chunker import chunk_sections
from backend.ingest.deduplicator import DeduplicationResult, PaperDeduplicator
from backend.ingest.downloader import DownloadError, PdfDownloader
from backend.ingest.embedder import EmbedderError, SentenceTransformerEmbedder
from backend.ingest.indexer import IndexWriteResult, IndexerError, PaperIndexer
from backend.ingest.parser import ParseError, parse_pdf
from backend.ingest.state_machine import InvalidPaperStatusTransition, validate_transition
from backend.ingest.structurer import StructuredPaper, structure_parse_result
from backend.storage.faiss_store import FaissStore
from backend.storage.file_store import PdfFileStore
from backend.storage.sqlite_store import SQLiteMetadataStore


@dataclass(frozen=True)
class StoredPdf:
    pdf_path: str
    pdf_hash: str
    file_size_bytes: int
    already_exists: bool


@dataclass(frozen=True)
class PipelineRunResult:
    job: IngestJob
    paper: Paper
    skipped: bool = False
    skip_reason: str | None = None


class PipelineFailure(RuntimeError):
    """Raised when a single-paper ingest run fails after state/job updates."""

    def __init__(
        self,
        ingest_error: IngestError,
        *,
        job: IngestJob,
        paper: Paper | None = None,
    ) -> None:
        super().__init__(ingest_error.error_message)
        self.ingest_error = ingest_error
        self.job = job
        self.paper = paper


class SinglePaperIngestPipeline:
    """Coordinate the Phase 1 single-paper ingest flow."""

    def __init__(
        self,
        *,
        settings: AppConfig | None = None,
        metadata_store: SQLiteMetadataStore | None = None,
        file_store: PdfFileStore | None = None,
        downloader: PdfDownloader | None = None,
        embedder: SentenceTransformerEmbedder | None = None,
        indexer: PaperIndexer | None = None,
        deduplicator: PaperDeduplicator | None = None,
    ) -> None:
        self._settings = settings or load_settings()
        self._settings.ensure_runtime_directories()
        configure_logging(self._settings)

        self._metadata_store = metadata_store or SQLiteMetadataStore()
        self._file_store = file_store or PdfFileStore(settings=self._settings)
        self._downloader = downloader or PdfDownloader(file_store=self._file_store)
        self._embedder = embedder or SentenceTransformerEmbedder(settings=self._settings)
        self._indexer = indexer or PaperIndexer(
            self._metadata_store,
            FaissStore(settings=self._settings),
        )
        self._deduplicator = deduplicator or PaperDeduplicator(self._metadata_store)
        self._logger = get_logger(__name__, component="single_ingest_pipeline")

    def ingest_from_url(
        self,
        url: str,
        *,
        doi: str | None = None,
        options: IngestOptions | None = None,
    ) -> PipelineRunResult:
        """Run the full ingest flow for a remote URL."""

        resolved = _resolve_remote_source(url)
        return self._run(
            source_label=url,
            source_url=resolved.source_url,
            pdf_url=resolved.pdf_url,
            local_pdf_path=None,
            doi=doi,
            options=options or IngestOptions(),
        )

    def ingest_from_local(
        self,
        pdf_path: str | Path,
        *,
        source_url: str | None = None,
        doi: str | None = None,
        options: IngestOptions | None = None,
    ) -> PipelineRunResult:
        """Run the full ingest flow for a local PDF path."""

        return self._run(
            source_label=str(pdf_path),
            source_url=source_url,
            pdf_url=source_url,
            local_pdf_path=Path(pdf_path).expanduser().resolve(),
            doi=doi,
            options=options or IngestOptions(),
        )

    def _run(
        self,
        *,
        source_label: str,
        source_url: str | None,
        pdf_url: str | None,
        local_pdf_path: Path | None,
        doi: str | None,
        options: IngestOptions,
    ) -> PipelineRunResult:
        job = self._create_job(source_label=source_label, options=options)
        current_paper: Paper | None = None
        created_new_paper = False

        try:
            existing = self._find_existing_paper(source_url=source_url, pdf_url=pdf_url, doi=doi)
            if existing is not None and not options.force_reparse:
                if options.skip_existing:
                    return self._complete_as_skipped(
                        job,
                        existing,
                        reason="existing_paper",
                    )
                raise self._fail(
                    job,
                    stage="queued",
                    error_code=DEDUP_CONFLICT,
                    message="Paper already exists in the local library.",
                    paper=existing,
                    details={"paper_id": existing.paper_id},
                )

            current_paper, created_new_paper = self._prepare_target_paper(
                existing=existing,
                source_url=source_url,
                pdf_url=pdf_url,
                doi=doi,
                force_reparse=options.force_reparse,
            )
            job = self._update_job(
                job,
                status="running",
                started_at=_utc_now_iso(),
                in_progress=1,
                paper_ids=[current_paper.paper_id],
            )
            current_paper = self._advance_status(current_paper, "queued")

            current_paper, stored_pdf = self._download_stage(
                job,
                current_paper,
                source_label=source_label,
                pdf_url=pdf_url,
                local_pdf_path=local_pdf_path,
            )

            existing_by_hash = self._find_existing_by_pdf_hash(
                stored_pdf.pdf_hash,
                exclude_paper_id=current_paper.paper_id,
            )
            if existing_by_hash is not None:
                if options.force_reparse:
                    current_paper, created_new_paper = self._adopt_existing_paper(
                        current_paper,
                        existing_by_hash,
                        created_new_paper=created_new_paper,
                    )
                elif options.skip_existing:
                    return self._complete_duplicate_skip(
                        job,
                        current_paper,
                        existing_by_hash,
                        created_new_paper=created_new_paper,
                        reason="pdf_hash",
                    )
                raise self._fail(
                    job,
                    stage="queued",
                    error_code=DEDUP_CONFLICT,
                    message="A paper with the same PDF already exists.",
                    paper=current_paper,
                    details={"paper_id": existing_by_hash.paper_id, "match_type": "pdf_hash"},
                )

            current_paper, parse_result = self._parse_stage(job, current_paper)
            structured = structure_parse_result(
                parse_result,
                source_url=source_url,
                source_pdf_url=pdf_url,
            )
            structured = self._apply_input_metadata(structured, doi=doi, pdf_url=pdf_url)

            duplicate = self._find_duplicate_candidate(
                structured.paper,
                exclude_paper_id=current_paper.paper_id,
            )
            if duplicate is not None:
                duplicate_paper = self._metadata_store.get_paper(duplicate.existing_paper_id or "")
                if duplicate_paper is not None and options.force_reparse:
                    current_paper, created_new_paper = self._adopt_existing_paper(
                        current_paper,
                        duplicate_paper,
                        created_new_paper=created_new_paper,
                    )
                elif duplicate_paper is not None and options.skip_existing:
                    return self._complete_duplicate_skip(
                        job,
                        current_paper,
                        duplicate_paper,
                        created_new_paper=created_new_paper,
                        reason=duplicate.match_type or "duplicate",
                    )
                raise self._fail(
                    job,
                    stage="queued",
                    error_code=DEDUP_CONFLICT,
                    message="A duplicate paper already exists in the local library.",
                    paper=current_paper,
                    details={
                        "paper_id": duplicate.existing_paper_id,
                        "match_type": duplicate.match_type,
                        "similarity": duplicate.similarity,
                    },
                )

            structured = self._remap_structured(structured, paper_id=current_paper.paper_id)
            current_paper = self._merge_structured_paper(
                current_paper,
                structured.paper,
                pdf_path=stored_pdf.pdf_path,
                pdf_hash=stored_pdf.pdf_hash,
            )
            sections = structured.sections

            self._record_parse_metrics(
                current_paper.paper_id,
                parse_result=parse_result,
                sections=sections,
                abstract=current_paper.abstract,
            )

            current_paper, chunks = self._chunk_stage(current_paper, sections)
            current_paper, embeddings = self._embedding_stage(job, current_paper, chunks)
            current_paper, index_result = self._index_stage(
                job,
                current_paper,
                sections=sections,
                chunks=chunks,
                embeddings=embeddings,
                replace_existing=options.force_reparse,
            )
            current_paper = self._ready_stage(job, current_paper, index_result=index_result)

            job = self._update_job(
                job,
                status="completed",
                completed_at=_utc_now_iso(),
                succeeded=1,
                failed=0,
                skipped=0,
                in_progress=0,
                paper_ids=[current_paper.paper_id],
                errors=[],
            )
            self._logger.info(
                "single_ingest_completed",
                job_id=job.job_id,
                paper_id=current_paper.paper_id,
                source=source_label,
            )
            return PipelineRunResult(job=job, paper=current_paper, skipped=False)
        except PipelineFailure:
            raise
        except Exception as exc:
            raise self._fail(
                job,
                stage=current_paper.status if current_paper is not None else "queued",
                error_code=SYSTEM_INTERNAL_ERROR,
                message="Single-paper ingest failed with an unexpected error.",
                paper=current_paper,
                details={"exception_type": type(exc).__name__},
            ) from exc

    def _create_job(self, *, source_label: str, options: IngestOptions) -> IngestJob:
        job = IngestJob(
            job_type="single",
            status="pending",
            paper_urls=[source_label],
            total_count=1,
            options=options,
        )
        return self._metadata_store.upsert_ingest_job(job)

    def _prepare_target_paper(
        self,
        *,
        existing: Paper | None,
        source_url: str | None,
        pdf_url: str | None,
        doi: str | None,
        force_reparse: bool,
    ) -> tuple[Paper, bool]:
        if existing is not None:
            try:
                validate_transition(existing.status, "queued")
            except InvalidPaperStatusTransition as exc:
                raise ValueError(
                    f"Paper '{existing.paper_id}' cannot be re-ingested from status '{existing.status}'."
                ) from exc

            target = existing.model_copy(
                update={
                    "doi": doi or existing.doi,
                    "url": source_url or existing.url,
                    "pdf_url": pdf_url or existing.pdf_url,
                    "updated_at": _utc_now_iso(),
                    "ingested_at": None if force_reparse else existing.ingested_at,
                }
            )
            target = self._metadata_store.upsert_paper(target)
            return target, False

        paper = Paper(
            title="Pending ingest",
            doi=doi,
            url=source_url,
            pdf_url=pdf_url,
            status="discovered",
        )
        return self._metadata_store.upsert_paper(paper), True

    def _find_existing_paper(
        self,
        *,
        source_url: str | None,
        pdf_url: str | None,
        doi: str | None,
    ) -> Paper | None:
        predicates = (
            ("doi", doi),
            ("url", source_url),
            ("pdf_url", pdf_url),
        )
        for column, value in predicates:
            if not value:
                continue
            row = self._metadata_store.connection.execute(
                f"SELECT paper_id FROM papers WHERE {column} = ? LIMIT 1",
                (value,),
            ).fetchone()
            if row is None:
                continue
            paper = self._metadata_store.get_paper(str(row["paper_id"]))
            if paper is not None:
                return paper
        return None

    def _find_existing_by_pdf_hash(
        self,
        pdf_hash: str,
        *,
        exclude_paper_id: str | None = None,
    ) -> Paper | None:
        query = "SELECT paper_id FROM papers WHERE pdf_hash = ?"
        params: list[object] = [pdf_hash]
        if exclude_paper_id is not None:
            query += " AND paper_id != ?"
            params.append(exclude_paper_id)
        query += " LIMIT 1"

        row = self._metadata_store.connection.execute(query, tuple(params)).fetchone()
        if row is None:
            return None
        return self._metadata_store.get_paper(str(row["paper_id"]))

    def _download_stage(
        self,
        job: IngestJob,
        paper: Paper,
        *,
        source_label: str,
        pdf_url: str | None,
        local_pdf_path: Path | None,
    ) -> tuple[Paper, StoredPdf]:
        stage = "downloading"
        paper = self._advance_status(paper, stage)
        started_at = time.perf_counter()
        self._record_stage_event(
            paper.paper_id,
            stage=stage,
            event="stage_start",
            metadata={"source": source_label},
        )

        try:
            if local_pdf_path is not None:
                pdf_path, pdf_hash, already_exists = self._file_store.save_file(local_pdf_path)
                file_size_bytes = local_pdf_path.stat().st_size
            else:
                result = self._downloader.download(pdf_url or source_label)
                pdf_path = result.pdf_path
                pdf_hash = result.pdf_hash
                file_size_bytes = result.file_size_bytes
                already_exists = result.already_exists
        except DownloadError as exc:
            raise self._fail(
                job,
                stage=stage,
                error_code=exc.error_code,
                message=exc.message,
                paper=paper,
            )
        except OSError as exc:
            raise self._fail(
                job,
                stage=stage,
                error_code=SYSTEM_INTERNAL_ERROR,
                message="Failed to copy the local PDF into managed storage.",
                paper=paper,
                details={"exception_type": type(exc).__name__},
            ) from exc

        duration_ms = _elapsed_ms(started_at)
        paper = self._advance_status(
            paper,
            "downloaded",
            pdf_path=pdf_path,
            pdf_hash=pdf_hash,
        )
        self._record_stage_event(
            paper.paper_id,
            stage=stage,
            event="stage_end",
            duration_ms=duration_ms,
            metadata={
                "pdf_path": pdf_path,
                "pdf_hash": pdf_hash,
                "file_size_bytes": file_size_bytes,
                "already_exists": already_exists,
            },
        )
        return paper, StoredPdf(
            pdf_path=pdf_path,
            pdf_hash=pdf_hash,
            file_size_bytes=file_size_bytes,
            already_exists=already_exists,
        )

    def _parse_stage(self, job: IngestJob, paper: Paper) -> tuple[Paper, dict[str, Any]]:
        stage = "parsing"
        paper = self._advance_status(paper, stage)
        started_at = time.perf_counter()
        self._record_stage_event(
            paper.paper_id,
            stage=stage,
            event="stage_start",
            metadata={"parser": "pymupdf"},
        )

        try:
            parse_result = parse_pdf(
                paper.pdf_path or "",
                paper_id=paper.paper_id,
                file_store=self._file_store,
            )
        except ParseError as exc:
            raise self._fail(
                job,
                stage=stage,
                error_code=exc.error_code,
                message=exc.message,
                paper=paper,
            )

        duration_ms = _elapsed_ms(started_at)
        paper = self._advance_status(
            paper,
            "parsed",
            updated_at=_utc_now_iso(),
        )
        self._record_stage_event(
            paper.paper_id,
            stage=stage,
            event="stage_end",
            duration_ms=duration_ms,
            metadata={
                "page_count": parse_result["page_count"],
                "char_count": parse_result["char_count"],
                "parser": parse_result["parser_used"],
            },
        )
        return paper, parse_result

    def _chunk_stage(self, paper: Paper, sections: list[Section]) -> tuple[Paper, list]:
        self._record_stage_event(
            paper.paper_id,
            stage="chunked",
            event="stage_start",
            metadata={"section_count": len(sections)},
        )
        started_at = time.perf_counter()
        chunks = chunk_sections(sections, embedding_model=self._embedder.model_name)
        duration_ms = _elapsed_ms(started_at)
        updated = self._advance_status(
            paper,
            "chunked",
            section_count=len(sections),
            chunk_count=len(chunks),
        )
        self._record_stage_event(
            updated.paper_id,
            stage="chunked",
            event="stage_end",
            duration_ms=duration_ms,
            metadata={"section_count": len(sections), "chunk_count": len(chunks)},
        )
        return updated, chunks

    def _embedding_stage(self, job: IngestJob, paper: Paper, chunks):
        paper = self._advance_status(paper, "embedding")
        started_at = time.perf_counter()
        self._record_stage_event(
            paper.paper_id,
            stage="embedding",
            event="stage_start",
            metadata={"model": self._embedder.model_name, "chunk_count": len(chunks)},
        )

        try:
            embeddings = self._embedder.embed_chunks(chunks)
        except EmbedderError as exc:
            raise self._fail(
                job,
                stage="embedding",
                error_code=exc.error_code,
                message=str(exc),
                paper=paper,
            )

        self._record_stage_event(
            paper.paper_id,
            stage="embedding",
            event="stage_end",
            duration_ms=_elapsed_ms(started_at),
            metadata={"vector_count": len(embeddings)},
        )
        return paper, embeddings

    def _index_stage(
        self,
        job: IngestJob,
        paper: Paper,
        *,
        sections: list[Section],
        chunks,
        embeddings,
        replace_existing: bool,
    ) -> tuple[Paper, IndexWriteResult]:
        started_at = time.perf_counter()
        self._record_stage_event(
            paper.paper_id,
            stage="indexed",
            event="stage_start",
            metadata={"replace_existing": replace_existing, "chunk_count": len(chunks)},
        )

        try:
            result = self._indexer.index_paper(
                paper,
                sections,
                chunks,
                embeddings,
                replace_existing=replace_existing,
            )
        except IndexerError as exc:
            raise self._fail(
                job,
                stage="indexed",
                error_code=exc.error_code,
                message=str(exc),
                paper=paper,
            )

        updated = self._advance_status(
            self._metadata_store.get_paper(paper.paper_id) or paper,
            "indexed",
            section_count=result.section_count,
            chunk_count=result.chunk_count,
        )
        self._record_stage_event(
            updated.paper_id,
            stage="indexed",
            event="stage_end",
            duration_ms=_elapsed_ms(started_at),
            metadata={
                "section_count": result.section_count,
                "chunk_count": result.chunk_count,
                "vector_count": result.vector_count,
            },
        )
        return updated, result

    def _ready_stage(
        self,
        job: IngestJob,
        paper: Paper,
        *,
        index_result: IndexWriteResult,
    ) -> Paper:
        if index_result.chunk_count != paper.chunk_count:
            raise self._fail(
                job,
                stage="indexed",
                error_code=SYSTEM_INTERNAL_ERROR,
                message="Indexed chunk count does not match the persisted paper metadata.",
                paper=paper,
                details={
                    "paper_chunk_count": paper.chunk_count,
                    "indexed_chunk_count": index_result.chunk_count,
                },
            )

        ready = self._advance_status(
            paper,
            "ready",
            ingested_at=_utc_now_iso(),
            updated_at=_utc_now_iso(),
        )
        self._record_stage_event(
            ready.paper_id,
            stage="ready",
            event="stage_end",
            metadata={
                "section_count": ready.section_count,
                "chunk_count": ready.chunk_count,
            },
        )
        return ready

    def _advance_status(self, paper: Paper, to_status: PaperStatus, **updates: Any) -> Paper:
        validate_transition(paper.status, to_status)
        updated = paper.model_copy(
            update={
                **updates,
                "status": to_status,
                "updated_at": _utc_now_iso(),
            }
        )
        persisted = self._metadata_store.upsert_paper(updated)
        self._record_stage_event(
            persisted.paper_id,
            stage=to_status,
            event="status_transition",
            metadata={"from_status": paper.status, "to_status": to_status},
        )
        return persisted

    def _complete_as_skipped(self, job: IngestJob, paper: Paper, *, reason: str) -> PipelineRunResult:
        completed = self._update_job(
            job,
            status="completed",
            completed_at=_utc_now_iso(),
            skipped=1,
            in_progress=0,
            paper_ids=[paper.paper_id],
            errors=[],
        )
        self._logger.info(
            "single_ingest_skipped",
            job_id=completed.job_id,
            paper_id=paper.paper_id,
            reason=reason,
        )
        return PipelineRunResult(
            job=completed,
            paper=paper,
            skipped=True,
            skip_reason=reason,
        )

    def _complete_duplicate_skip(
        self,
        job: IngestJob,
        temporary_paper: Paper,
        existing_paper: Paper,
        *,
        created_new_paper: bool,
        reason: str,
    ) -> PipelineRunResult:
        if created_new_paper:
            self._delete_paper(temporary_paper.paper_id)
        return self._complete_as_skipped(job, existing_paper, reason=reason)

    def _fail(
        self,
        job: IngestJob,
        *,
        stage: PaperStatus,
        error_code: str,
        message: str,
        paper: Paper | None,
        details: dict[str, Any] | None = None,
    ) -> PipelineFailure:
        updated_paper = paper
        if paper is not None and paper.status in {"downloading", "parsing", "embedding", "indexed"}:
            updated_paper = self._advance_status(paper, "failed")

        ingest_error = IngestError(
            url=(paper.url if paper is not None and paper.url else job.paper_urls[0]),
            stage=stage,
            error_code=error_code,
            error_message=message,
            retryable=is_retryable_error(error_code),
        )
        updated_job = self._update_job(
            job,
            status="failed",
            completed_at=_utc_now_iso(),
            failed=1,
            in_progress=0,
            paper_ids=[] if updated_paper is None else [updated_paper.paper_id],
            errors=[ingest_error],
        )
        if updated_paper is not None:
            self._record_stage_event(
                updated_paper.paper_id,
                stage=stage,
                event="stage_error",
                metadata=details or {},
                error=ingest_error,
            )
        self._logger.error(
            "single_ingest_failed",
            job_id=updated_job.job_id,
            paper_id=None if updated_paper is None else updated_paper.paper_id,
            stage=stage,
            error_code=error_code,
        )
        return PipelineFailure(ingest_error, job=updated_job, paper=updated_paper)

    def _apply_input_metadata(
        self,
        structured: StructuredPaper,
        *,
        doi: str | None,
        pdf_url: str | None,
    ) -> StructuredPaper:
        updated_paper = structured.paper.model_copy(
            update={
                "doi": doi or structured.paper.doi,
                "pdf_url": pdf_url or structured.paper.pdf_url,
            }
        )
        return StructuredPaper(paper=updated_paper, sections=structured.sections)

    def _find_duplicate_candidate(
        self,
        paper: Paper,
        *,
        exclude_paper_id: str,
    ) -> DeduplicationResult | None:
        duplicate = self._deduplicator.find_duplicate(paper)
        if not duplicate.is_duplicate:
            return None
        if duplicate.existing_paper_id == exclude_paper_id:
            return None
        return duplicate

    def _adopt_existing_paper(
        self,
        current_paper: Paper,
        existing_paper: Paper,
        *,
        created_new_paper: bool,
    ) -> tuple[Paper, bool]:
        if created_new_paper:
            self._delete_paper(current_paper.paper_id)

        try:
            validate_transition(existing_paper.status, "queued")
        except InvalidPaperStatusTransition as exc:
            raise ValueError(
                f"Paper '{existing_paper.paper_id}' cannot be re-ingested from status '{existing_paper.status}'."
            ) from exc

        adopted = self._advance_status(
            existing_paper,
            "queued",
            pdf_path=current_paper.pdf_path,
            pdf_hash=current_paper.pdf_hash,
        )
        adopted = self._advance_status(adopted, "downloading")
        adopted = self._advance_status(
            adopted,
            "downloaded",
            pdf_path=current_paper.pdf_path,
            pdf_hash=current_paper.pdf_hash,
        )
        return adopted, False

    def _remap_structured(self, structured: StructuredPaper, *, paper_id: str) -> StructuredPaper:
        updated_paper = structured.paper.model_copy(update={"paper_id": paper_id})
        updated_sections = [section.model_copy(update={"paper_id": paper_id}) for section in structured.sections]
        return StructuredPaper(paper=updated_paper, sections=updated_sections)

    def _merge_structured_paper(
        self,
        current_paper: Paper,
        structured_paper: Paper,
        *,
        pdf_path: str,
        pdf_hash: str,
    ) -> Paper:
        merged = current_paper.model_copy(
            update={
                "title": structured_paper.title,
                "authors": structured_paper.authors,
                "abstract": structured_paper.abstract,
                "year": structured_paper.year,
                "venue": structured_paper.venue,
                "keywords": structured_paper.keywords,
                "url": structured_paper.url or current_paper.url,
                "pdf_url": structured_paper.pdf_url or current_paper.pdf_url,
                "doi": structured_paper.doi or current_paper.doi,
                "section_count": structured_paper.section_count,
                "pdf_path": pdf_path,
                "pdf_hash": pdf_hash,
                "updated_at": _utc_now_iso(),
            }
        )
        return self._metadata_store.upsert_paper(merged)

    def _record_parse_metrics(
        self,
        paper_id: str,
        *,
        parse_result: dict[str, Any],
        sections: list[Section],
        abstract: str,
    ) -> None:
        page_count = int(parse_result["page_count"])
        char_count = int(parse_result["char_count"])
        reference_count = len(parse_result.get("references_raw", []))
        has_references = any(section.section_type == "references" for section in sections)

        with self._metadata_store.connection:
            self._metadata_store.connection.execute(
                """
                INSERT OR REPLACE INTO parse_metrics (
                    paper_id,
                    parser_used,
                    page_count,
                    extracted_char_count,
                    chars_per_page,
                    section_count,
                    has_abstract,
                    has_references,
                    reference_count,
                    figure_count,
                    table_count,
                    encoding_issues,
                    confidence,
                    recorded_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    paper_id,
                    parse_result["parser_used"],
                    page_count,
                    char_count,
                    0.0 if page_count == 0 else char_count / page_count,
                    len(sections),
                    1 if abstract.strip() else 0,
                    1 if has_references else 0,
                    reference_count,
                    0,
                    0,
                    1 if parse_result.get("encoding_issues") else 0,
                    parse_result.get("confidence"),
                    _utc_now_iso(),
                ),
            )

    def _record_stage_event(
        self,
        paper_id: str,
        *,
        stage: PaperStatus,
        event: str,
        duration_ms: int | None = None,
        metadata: dict[str, Any] | None = None,
        error: IngestError | None = None,
    ) -> None:
        payload = {
            "timestamp": _utc_now_iso(),
            "paper_id": paper_id,
            "stage": stage,
            "event": event,
            "duration_ms": duration_ms,
            "details": metadata or {},
            "error": None if error is None else error.model_dump(),
        }

        with self._metadata_store.connection:
            self._metadata_store.connection.execute(
                """
                INSERT INTO paper_traces (
                    paper_id,
                    timestamp,
                    stage,
                    event,
                    duration_ms,
                    metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    paper_id,
                    payload["timestamp"],
                    stage,
                    event,
                    duration_ms,
                    json.dumps(payload["details"], sort_keys=True),
                ),
            )

        log_path = self._settings.paths.ingest_logs_dir / f"{payload['timestamp'][:10]}.jsonl"
        with log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, sort_keys=True) + "\n")

        if event == "stage_error":
            self._logger.error("ingest_stage_event", **payload)
        else:
            self._logger.info("ingest_stage_event", **payload)

    def _update_job(self, job: IngestJob, **updates: Any) -> IngestJob:
        return self._metadata_store.upsert_ingest_job(job.model_copy(update=updates))

    def _delete_paper(self, paper_id: str) -> None:
        with self._metadata_store.connection:
            self._metadata_store.connection.execute("DELETE FROM papers WHERE paper_id = ?", (paper_id,))


@dataclass(frozen=True)
class RemoteSource:
    source_url: str
    pdf_url: str


def _resolve_remote_source(url: str) -> RemoteSource:
    normalized = url.strip()
    parsed = urlparse(normalized)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError(f"Invalid ingest URL: {url}")

    if parsed.netloc.endswith("arxiv.org") and parsed.path.startswith("/abs/"):
        paper_id = parsed.path.removeprefix("/abs/")
        return RemoteSource(source_url=normalized, pdf_url=f"https://arxiv.org/pdf/{paper_id}.pdf")

    return RemoteSource(source_url=normalized, pdf_url=normalized)


def ingest_from_url(
    url: str,
    *,
    doi: str | None = None,
    options: IngestOptions | None = None,
    pipeline: SinglePaperIngestPipeline | None = None,
) -> PipelineRunResult:
    """Convenience wrapper for a remote single-paper ingest."""

    runner = pipeline or SinglePaperIngestPipeline()
    return runner.ingest_from_url(url, doi=doi, options=options)


def ingest_from_local(
    pdf_path: str | Path,
    *,
    source_url: str | None = None,
    doi: str | None = None,
    options: IngestOptions | None = None,
    pipeline: SinglePaperIngestPipeline | None = None,
) -> PipelineRunResult:
    """Convenience wrapper for a local single-paper ingest."""

    runner = pipeline or SinglePaperIngestPipeline()
    return runner.ingest_from_local(
        pdf_path,
        source_url=source_url,
        doi=doi,
        options=options,
    )


def _utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _elapsed_ms(started_at: float) -> int:
    return int((time.perf_counter() - started_at) * 1000)
