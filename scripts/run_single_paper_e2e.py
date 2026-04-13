#!/usr/bin/env python3
"""Ingest a single paper, analyze it with the configured LLM, and report timings."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path
from time import perf_counter

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from backend.analysis.single_paper import SinglePaperAnalysisError, SinglePaperAnalyzer
from backend.common.models import IngestOptions
from backend.ingest.pipeline import PipelineFailure, SinglePaperIngestPipeline
from backend.storage.sqlite_store import SQLiteMetadataStore


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--url", help="Remote paper URL or arXiv abs URL.")
    source.add_argument("--pdf-path", help="Local PDF path to ingest.")
    parser.add_argument("--source-url", default=None, help="Optional canonical source URL for local PDF ingest.")
    parser.add_argument("--focus", default=None, help="Optional analysis focus, such as methodology or limitations.")
    parser.add_argument("--user-query", default=None, help="Optional user question to steer the analysis.")
    parser.add_argument("--force-reparse", action="store_true", help="Re-run ingest even if the paper already exists.")
    parser.add_argument("--no-skip-existing", action="store_true", help="Fail instead of skipping duplicates.")
    parser.add_argument("--json", action="store_true", help="Print the full result payload as JSON.")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    pipeline = SinglePaperIngestPipeline()
    ingest_options = IngestOptions(
        skip_existing=not args.no_skip_existing,
        force_reparse=args.force_reparse,
    )
    store = pipeline._metadata_store  # noqa: SLF001 - script-level orchestration helper
    trace_cursor = _current_trace_cursor(store)
    analyzer = SinglePaperAnalyzer(
        settings=pipeline._settings,  # noqa: SLF001 - script-level orchestration helper
        metadata_store=store,
        vector_store=pipeline._indexer._vector_store,  # noqa: SLF001 - share live index
        embedder=pipeline._embedder,  # noqa: SLF001 - share configured embedder
    )

    ingest_started_at = perf_counter()
    try:
        if args.url:
            ingest_result = pipeline.ingest_from_url(
                args.url,
                options=ingest_options,
            )
        else:
            ingest_result = pipeline.ingest_from_local(
                args.pdf_path,
                source_url=args.source_url,
                options=ingest_options,
            )
    except PipelineFailure as exc:
        payload = {
            "ok": False,
            "stage": "ingest",
            "error_code": exc.ingest_error.error_code,
            "error_message": exc.ingest_error.error_message,
            "job_id": exc.job.job_id,
            "paper_id": None if exc.paper is None else exc.paper.paper_id,
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2 if args.json else None))
        return 1
    ingest_duration_ms = _elapsed_ms(ingest_started_at)

    analysis_started_at = perf_counter()
    try:
        analysis_response = analyzer.analyze(
            paper_id=ingest_result.paper.paper_id,
            focus=args.focus,
            user_query=args.user_query,
        )
    except SinglePaperAnalysisError as exc:
        payload = {
            "ok": False,
            "stage": "analysis",
            "error_code": exc.error_code,
            "error_message": str(exc),
            "job_id": ingest_result.job.job_id,
            "paper_id": ingest_result.paper.paper_id,
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2 if args.json else None))
        return 1
    analysis_duration_ms = _elapsed_ms(analysis_started_at)

    stage_timings = _load_stage_timings(store, ingest_result.paper.paper_id)
    current_stage_timings = _load_stage_timings(
        store,
        ingest_result.paper.paper_id,
        min_trace_id=trace_cursor,
    )
    payload = {
        "ok": True,
        "job_id": ingest_result.job.job_id,
        "paper_id": ingest_result.paper.paper_id,
        "paper_title": ingest_result.paper.title,
        "skipped": ingest_result.skipped,
        "ingest_duration_ms": ingest_duration_ms,
        "analysis_duration_ms": analysis_duration_ms,
        "analysis_metrics": asdict(analysis_response.metrics),
        "stage_timings_ms": current_stage_timings,
        "historical_stage_timings_ms": stage_timings,
        "result": analysis_response.result.model_dump(),
    }

    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    print(f"[ok] paper_id={payload['paper_id']} skipped={payload['skipped']}")
    print(f"title: {payload['paper_title']}")
    print("ingest_duration_ms:", payload["ingest_duration_ms"])
    print("analysis_duration_ms:", payload["analysis_duration_ms"])
    print("stage_timings_ms:", json.dumps(stage_timings, ensure_ascii=False))
    print("analysis_metrics:", json.dumps(payload["analysis_metrics"], ensure_ascii=False))
    print("summary:", analysis_response.result.summary)
    return 0


def _current_trace_cursor(store: SQLiteMetadataStore) -> int:
    row = store.connection.execute("SELECT COALESCE(MAX(trace_id), 0) AS max_trace_id FROM paper_traces").fetchone()
    return int(row["max_trace_id"] if row is not None else 0)


def _load_stage_timings(
    store: SQLiteMetadataStore,
    paper_id: str,
    *,
    min_trace_id: int = 0,
) -> dict[str, int]:
    rows = store.connection.execute(
        """
        SELECT stage, SUM(COALESCE(duration_ms, 0)) AS total_duration_ms
        FROM paper_traces
        WHERE paper_id = ? AND event = 'stage_end' AND trace_id > ?
        GROUP BY stage
        ORDER BY MIN(trace_id) ASC
        """,
        (paper_id, min_trace_id),
    ).fetchall()
    return {str(row["stage"]): int(row["total_duration_ms"] or 0) for row in rows}


def _elapsed_ms(started_at: float) -> int:
    return max(0, int(round((perf_counter() - started_at) * 1000)))


if __name__ == "__main__":
    raise SystemExit(main())
