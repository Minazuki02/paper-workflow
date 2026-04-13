"""Minimal ingest MCP tool handlers for the Phase 1 search slice."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import PurePosixPath
from urllib.parse import urlparse
from typing import Any

from pydantic import ValidationError

from backend.common.errors import (
    DEDUP_CONFLICT,
    INGEST_BATCH_TOO_LARGE,
    INGEST_DEDUP_CONFLICT,
    INGEST_INVALID_URL,
    SEARCH_API_ERROR,
    SEARCH_INVALID_QUERY,
    STATUS_NOT_FOUND,
    SYSTEM_INTERNAL_ERROR,
    build_tool_error,
)
from backend.common.models import IngestJob, IngestOptions, PaperStatus
from backend.ingest.downloader import DownloadError, PdfDownloader
from backend.ingest.pipeline import PipelineFailure, SinglePaperIngestPipeline
from backend.search.arxiv_provider import ArxivSearchProvider
from backend.search.base import SearchProvider, SearchProviderError, SearchQuery, SearchResponse, SearchResult
from backend.search.s2_provider import SemanticScholarProvider
from backend.storage.sqlite_store import SQLiteMetadataStore


def handle_search_papers(
    *,
    query: str,
    source: str = "all",
    year_from: int | None = None,
    year_to: int | None = None,
    max_results: int = 20,
    sort_by: str = "relevance",
    provider: SearchProvider | None = None,
    metadata_store: SQLiteMetadataStore | None = None,
    s2_api_key: str | None = None,
) -> dict[str, Any]:
    """Validate input, call search provider(s), and annotate library presence."""

    try:
        search_request = SearchQuery(
            query=query,
            source=source,
            year_from=year_from,
            year_to=year_to,
            max_results=max_results,
            sort_by=sort_by,
        )
    except ValidationError as exc:
        return build_tool_error(
            SEARCH_INVALID_QUERY,
            details={"validation_error": exc.errors(include_url=False)},
        ).model_dump()

    store = metadata_store or SQLiteMetadataStore()

    if provider is not None:
        return _search_single_provider(provider, search_request, store)

    if search_request.source == "arxiv":
        return _search_single_provider(ArxivSearchProvider(), search_request, store)

    if search_request.source == "semantic_scholar":
        return _search_single_provider(
            SemanticScholarProvider(api_key=s2_api_key), search_request, store,
        )

    # source == "all": fan out to both providers, merge results
    return _search_all_providers(search_request, store, s2_api_key=s2_api_key)


def _search_single_provider(
    provider: SearchProvider,
    search_request: SearchQuery,
    store: SQLiteMetadataStore,
) -> dict[str, Any]:
    try:
        response = provider.search(search_request)
    except SearchProviderError as exc:
        return build_tool_error(
            exc.error_code,
            error_message=exc.message,
            details={"source": provider.source_name},
        ).model_dump()

    return _annotate_and_respond(response, store)


def _search_all_providers(
    search_request: SearchQuery,
    store: SQLiteMetadataStore,
    *,
    s2_api_key: str | None = None,
) -> dict[str, Any]:
    providers: list[SearchProvider] = [
        ArxivSearchProvider(),
        SemanticScholarProvider(api_key=s2_api_key),
    ]

    all_results: list[SearchResult] = []
    sources_used: list[str] = []
    total_found = 0

    for provider in providers:
        try:
            response = provider.search(search_request)
        except SearchProviderError:
            continue
        all_results.extend(response.results)
        total_found += response.total_found
        sources_used.append(response.source_used)

    if not sources_used:
        return build_tool_error(
            SEARCH_API_ERROR,
            error_message="All search providers failed.",
            details={"attempted_sources": [p.source_name for p in providers]},
        ).model_dump()

    deduped = _deduplicate_results(all_results)
    trimmed = deduped[:search_request.max_results]

    return _annotate_and_respond(
        SearchResponse(
            results=trimmed,
            total_found=total_found,
            source_used="+".join(sources_used),
        ),
        store,
    )


def _deduplicate_results(results: list[SearchResult]) -> list[SearchResult]:
    """Remove duplicate papers across providers by DOI or normalized title."""
    seen_keys: set[str] = set()
    deduped: list[SearchResult] = []

    for result in results:
        keys: list[str] = []
        if result.doi:
            keys.append(f"doi:{result.doi.lower()}")
        keys.append(f"title:{result.title.lower().strip()}")

        if any(k in seen_keys for k in keys):
            continue
        seen_keys.update(keys)
        deduped.append(result)

    return deduped


def _annotate_and_respond(
    response: SearchResponse, store: SQLiteMetadataStore,
) -> dict[str, Any]:
    annotated_results = [
        result.model_copy(update={"already_ingested": _is_already_ingested(result, store)})
        for result in response.results
    ]
    return SearchResponse(
        results=annotated_results,
        total_found=response.total_found,
        source_used=response.source_used,
    ).model_dump()


def _is_already_ingested(result: SearchResult, store: SQLiteMetadataStore) -> bool:
    arxiv_id = _extract_arxiv_id(result.url) or _extract_arxiv_id(result.pdf_url)
    predicates = [
        ("doi = ?", result.doi),
        ("url = ?", result.url),
        ("pdf_url = ?", result.pdf_url),
        ("arxiv_id = ?", arxiv_id),
    ]

    for clause, value in predicates:
        if not value:
            continue
        row = store.connection.execute(
            f"SELECT 1 FROM papers WHERE {clause} LIMIT 1",
            (value,),
        ).fetchone()
        if row is not None:
            return True

    return False


def _extract_arxiv_id(url: str | None) -> str | None:
    if not url:
        return None

    path = PurePosixPath(url.split("?", 1)[0])
    if len(path.parts) < 3 or path.parts[1] not in {"abs", "pdf"}:
        return None

    identifier = path.parts[2]
    if identifier.endswith(".pdf"):
        identifier = identifier[:-4]
    return identifier or None


def handle_fetch_pdf(
    *,
    url: str,
    filename: str | None = None,
    downloader: PdfDownloader | None = None,
) -> dict[str, Any]:
    """Download a single PDF to local storage without triggering ingest."""

    pdf_downloader = downloader or PdfDownloader()

    try:
        result = pdf_downloader.download(url, filename=filename)
    except DownloadError as exc:
        return build_tool_error(exc.error_code, error_message=exc.message).model_dump()

    return {
        "success": True,
        "pdf_path": result.pdf_path,
        "file_size_bytes": result.file_size_bytes,
        "pdf_hash": result.pdf_hash,
        "already_exists": result.already_exists,
    }


def handle_ingest_paper(
    *,
    url: str,
    doi: str | None = None,
    skip_if_exists: bool = True,
    parser: str = "pymupdf",
    pipeline: SinglePaperIngestPipeline | None = None,
) -> dict[str, Any]:
    """Run the single-paper ingest pipeline and expose the async-style MCP contract."""

    if not _is_supported_remote_url(url):
        return build_tool_error(
            INGEST_INVALID_URL,
            details={"url": url},
        ).model_dump()

    try:
        options = IngestOptions(skip_existing=skip_if_exists, parser=parser)
    except ValidationError as exc:
        return build_tool_error(
            INGEST_INVALID_URL,
            error_message="Invalid ingest options supplied.",
            retryable=False,
            details={"validation_error": exc.errors(include_url=False)},
        ).model_dump()

    ingest_pipeline = pipeline or SinglePaperIngestPipeline()

    try:
        result = ingest_pipeline.ingest_from_url(url, doi=doi, options=options)
    except PipelineFailure as exc:
        return build_tool_error(
            _normalize_ingest_error_code(exc.ingest_error.error_code),
            error_message=exc.ingest_error.error_message,
            retryable=exc.ingest_error.retryable,
            details={
                "job_id": exc.job.job_id,
                "paper_id": None if exc.paper is None else exc.paper.paper_id,
                "stage": exc.ingest_error.stage,
            },
        ).model_dump()
    except Exception as exc:  # pragma: no cover - defensive fallback
        return build_tool_error(
            SYSTEM_INTERNAL_ERROR,
            details={"exception_type": type(exc).__name__},
        ).model_dump()

    if result.skipped:
        return {
            "job_id": result.job.job_id,
            "paper_id": result.paper.paper_id,
            "status": "skipped",
            "message": "Paper already exists in the local library and was skipped.",
        }

    return {
        "job_id": result.job.job_id,
        "paper_id": None,
        "status": "queued",
        "message": "Paper ingest job accepted. Query get_ingest_status with the job_id for progress.",
    }


def handle_get_ingest_status(
    *,
    job_id: str | None = None,
    paper_id: str | None = None,
    metadata_store: SQLiteMetadataStore | None = None,
) -> dict[str, Any]:
    """Return ingest status for either a job or a single paper."""

    if (job_id is None and paper_id is None) or (job_id is not None and paper_id is not None):
        return build_tool_error(
            STATUS_NOT_FOUND,
            error_message="Provide exactly one of job_id or paper_id.",
            details={"job_id": job_id, "paper_id": paper_id},
        ).model_dump()

    store = metadata_store or SQLiteMetadataStore()

    if job_id is not None:
        job = store.get_ingest_job(job_id)
        if job is None:
            return build_tool_error(STATUS_NOT_FOUND, details={"job_id": job_id}).model_dump()

        current_stage = _derive_job_stage(job, store)
        return {
            "job": job.model_dump(),
            "paper": None,
            "current_stage": current_stage,
            "progress": _job_progress_message(job),
            "errors": [error.model_dump() for error in job.errors],
            "retry_count": 0,
            "estimated_remaining_sec": None,
        }

    paper = store.get_paper(paper_id or "")
    if paper is None:
        return build_tool_error(STATUS_NOT_FOUND, details={"paper_id": paper_id}).model_dump()

    errors = _paper_errors(paper.paper_id, store)
    return {
        "job": None,
        "paper": _paper_status_payload(paper),
        "current_stage": paper.status,
        "progress": _paper_progress_message(paper.status),
        "errors": [error.model_dump() for error in errors],
        "retry_count": _paper_retry_count(paper.paper_id, store),
        "estimated_remaining_sec": None,
    }


def handle_batch_ingest(
    *,
    urls: list[str],
    options: dict[str, Any] | IngestOptions | None = None,
    pipeline: SinglePaperIngestPipeline | None = None,
    metadata_store: SQLiteMetadataStore | None = None,
) -> dict[str, Any]:
    """Run sequential batch ingest while exposing a stable batch-job contract."""

    if len(urls) > 100:
        return build_tool_error(
            INGEST_BATCH_TOO_LARGE,
            details={"url_count": len(urls), "max_allowed": 100},
        ).model_dump()

    try:
        ingest_options = (
            options
            if isinstance(options, IngestOptions)
            else IngestOptions.model_validate(options or {})
        )
    except ValidationError as exc:
        return build_tool_error(
            SYSTEM_INTERNAL_ERROR,
            error_message="Invalid batch ingest options supplied.",
            retryable=False,
            details={"validation_error": exc.errors(include_url=False)},
        ).model_dump()

    store = _resolve_metadata_store(metadata_store, pipeline)
    ingest_pipeline = pipeline or SinglePaperIngestPipeline(metadata_store=store)

    batch_job = store.upsert_ingest_job(
        IngestJob(
            job_type="batch",
            status="pending",
            paper_urls=urls,
            total_count=len(urls),
            options=ingest_options,
        )
    )

    queued_urls: list[str] = []
    skipped_urls: list[dict[str, str | None]] = []
    seen_urls: set[str] = set()

    for raw_url in urls:
        normalized_url = raw_url.strip()
        if not _is_supported_remote_url(normalized_url):
            skipped_urls.append(
                {"url": raw_url, "reason": "invalid_url", "existing_paper_id": None}
            )
            continue

        if normalized_url in seen_urls:
            skipped_urls.append(
                {"url": raw_url, "reason": "duplicate_in_batch", "existing_paper_id": None}
            )
            continue
        seen_urls.add(normalized_url)

        existing_paper = _find_existing_paper_for_url(normalized_url, store)
        if existing_paper is not None and ingest_options.skip_existing and not ingest_options.force_reparse:
            skipped_urls.append(
                {
                    "url": raw_url,
                    "reason": "already_exists",
                    "existing_paper_id": existing_paper.paper_id,
                }
            )
            continue

        queued_urls.append(normalized_url)

    batch_job = _update_batch_job(
        store,
        batch_job,
        status="running" if queued_urls else "completed",
        started_at=batch_job.started_at or _utc_now_iso(),
        skipped=len(skipped_urls),
        in_progress=0 if not queued_urls else batch_job.in_progress,
    )

    paper_ids: list[str] = list(batch_job.paper_ids)
    errors = list(batch_job.errors)
    succeeded = batch_job.succeeded
    failed = batch_job.failed
    skipped = batch_job.skipped

    for queued_url in queued_urls:
        batch_job = _update_batch_job(store, batch_job, in_progress=1)
        try:
            result = ingest_pipeline.ingest_from_url(queued_url, options=ingest_options)
        except PipelineFailure as exc:
            failed += 1
            errors.append(exc.ingest_error)
            batch_job = _update_batch_job(
                store,
                batch_job,
                failed=failed,
                errors=errors,
                in_progress=0,
            )
            continue

        if result.skipped:
            skipped += 1
            skipped_urls.append(
                {
                    "url": queued_url,
                    "reason": "already_exists",
                    "existing_paper_id": result.paper.paper_id,
                }
            )
            batch_job = _update_batch_job(
                store,
                batch_job,
                skipped=skipped,
                in_progress=0,
            )
            continue

        succeeded += 1
        paper_ids.append(result.paper.paper_id)
        batch_job = _update_batch_job(
            store,
            batch_job,
            succeeded=succeeded,
            paper_ids=paper_ids,
            in_progress=0,
        )

    final_status = _finalize_batch_status(
        total_count=len(urls),
        succeeded=succeeded,
        failed=failed,
        skipped=skipped,
    )
    batch_job = _update_batch_job(
        store,
        batch_job,
        status=final_status,
        completed_at=_utc_now_iso(),
        succeeded=succeeded,
        failed=failed,
        skipped=skipped,
        in_progress=0,
        paper_ids=paper_ids,
        errors=errors,
    )

    return {
        "job_id": batch_job.job_id,
        "total_count": batch_job.total_count,
        "queued_count": len(queued_urls),
        "skipped_count": len(skipped_urls),
        "skipped_urls": skipped_urls,
    }


def _is_supported_remote_url(url: str) -> bool:
    parsed = urlparse(url.strip())
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _normalize_ingest_error_code(error_code: str) -> str:
    if error_code == DEDUP_CONFLICT:
        return INGEST_DEDUP_CONFLICT
    return error_code


def _derive_job_stage(job, store: SQLiteMetadataStore) -> PaperStatus:
    papers = [store.get_paper(paper_id) for paper_id in job.paper_ids]
    available = [paper for paper in papers if paper is not None]
    if available:
        if any(paper.status == "failed" for paper in available) and job.status in {"failed", "partial"}:
            return "failed"
        return max(available, key=lambda paper: _STATUS_ORDER[paper.status]).status
    if job.status == "completed":
        return "ready"
    if job.status == "failed":
        return "failed"
    return "queued"


def _job_progress_message(job) -> str:
    finished = job.succeeded + job.failed + job.skipped
    if job.status == "completed":
        return (
            f"Job completed: {job.succeeded} succeeded, {job.failed} failed, "
            f"{job.skipped} skipped out of {job.total_count}."
        )
    if job.status == "partial":
        return (
            f"Job partially completed: {job.succeeded} succeeded, {job.failed} failed, "
            f"{job.skipped} skipped out of {job.total_count}."
        )
    if job.status == "failed":
        return (
            f"Job failed after processing {finished} of {job.total_count} papers."
        )
    return (
        f"Job in progress: {finished} finished, {job.in_progress} in progress, "
        f"{max(job.total_count - finished - job.in_progress, 0)} pending."
    )


def _paper_progress_message(status: PaperStatus) -> str:
    return _PAPER_PROGRESS_MESSAGES.get(status, f"Paper is currently in stage '{status}'.")


def _paper_status_payload(paper) -> dict[str, Any]:
    return paper.model_dump(
        include={
            "paper_id",
            "title",
            "status",
            "ingested_at",
            "updated_at",
            "chunk_count",
            "section_count",
            "citation_count",
            "url",
            "doi",
            "arxiv_id",
            "year",
            "venue",
        }
    )


def _paper_errors(paper_id: str, store: SQLiteMetadataStore):
    jobs = store.list_ingest_jobs(limit=1000)
    relevant_errors = []
    for job in jobs:
        if paper_id not in job.paper_ids:
            continue
        relevant_errors.extend(job.errors)
    return relevant_errors[:1]


def _paper_retry_count(paper_id: str, store: SQLiteMetadataStore) -> int:
    return sum(
        1
        for job in store.list_ingest_jobs(limit=1000)
        if job.status == "failed" and paper_id in job.paper_ids
    )


def _resolve_metadata_store(
    metadata_store: SQLiteMetadataStore | None,
    pipeline: SinglePaperIngestPipeline | None,
) -> SQLiteMetadataStore:
    if metadata_store is not None:
        return metadata_store
    if pipeline is not None and hasattr(pipeline, "_metadata_store"):
        return getattr(pipeline, "_metadata_store")
    return SQLiteMetadataStore()


def _find_existing_paper_for_url(url: str, store: SQLiteMetadataStore):
    arxiv_id = _extract_arxiv_id(url)
    predicates = [
        ("url = ?", url),
        ("pdf_url = ?", url),
        ("arxiv_id = ?", arxiv_id),
    ]

    for clause, value in predicates:
        if not value:
            continue
        row = store.connection.execute(
            f"SELECT paper_id FROM papers WHERE {clause} LIMIT 1",
            (value,),
        ).fetchone()
        if row is None:
            continue
        paper = store.get_paper(str(row["paper_id"]))
        if paper is not None:
            return paper
    return None


def _update_batch_job(store: SQLiteMetadataStore, job, **updates):
    return store.upsert_ingest_job(job.model_copy(update=updates))


def _finalize_batch_status(*, total_count: int, succeeded: int, failed: int, skipped: int) -> str:
    if failed == 0:
        return "completed"
    if succeeded == 0 and skipped == 0 and total_count > 0:
        return "failed"
    return "partial"


_STATUS_ORDER: dict[PaperStatus, int] = {
    "discovered": 0,
    "queued": 1,
    "downloading": 2,
    "downloaded": 3,
    "parsing": 4,
    "parsed": 5,
    "chunked": 6,
    "embedding": 7,
    "indexed": 8,
    "ready": 9,
    "failed": 10,
    "archived": 11,
}

_PAPER_PROGRESS_MESSAGES: dict[PaperStatus, str] = {
    "discovered": "Paper record created and waiting to be queued for ingest.",
    "queued": "Paper is queued for ingest.",
    "downloading": "Downloading PDF bytes into managed storage.",
    "downloaded": "PDF download completed and parsing will start next.",
    "parsing": "PDF is being parsed into raw text.",
    "parsed": "Parsing finished and text is being structured into sections.",
    "chunked": "Sections were chunked and embeddings will be generated next.",
    "embedding": "Embedding generation is currently running.",
    "indexed": "Vectors and metadata were indexed; finalization is pending.",
    "ready": "Paper ingest completed successfully and the paper is ready.",
    "failed": "Paper ingest failed. Review the reported errors for retry guidance.",
    "archived": "Paper is archived and not active in the ingest workflow.",
}


def _utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
