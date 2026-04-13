"""Contract tests for Phase 1 ingest MCP tool surfaces."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.common.models import IngestJob, Paper
from backend.ingest.mcp_server import create_server
from backend.ingest.pipeline import PipelineRunResult
from backend.ingest.tools import handle_ingest_paper


class StubPipeline:
    def ingest_from_url(self, url: str, *, doi: str | None = None, options=None) -> PipelineRunResult:
        job = IngestJob(job_type="single", total_count=1, paper_urls=[url], paper_ids=["paper-123"])
        paper = Paper(
            paper_id="paper-123",
            title="Queued Paper",
            status="ready",
            url=url,
            doi=doi,
        )
        return PipelineRunResult(job=job, paper=paper, skipped=False)


class SkippingPipeline:
    def ingest_from_url(self, url: str, *, doi: str | None = None, options=None) -> PipelineRunResult:
        job = IngestJob(job_type="single", total_count=1, paper_urls=[url], paper_ids=["paper-456"])
        paper = Paper(
            paper_id="paper-456",
            title="Existing Paper",
            status="ready",
            url=url,
            doi=doi,
        )
        return PipelineRunResult(job=job, paper=paper, skipped=True, skip_reason="existing_paper")


def test_server_registers_task21_tools() -> None:
    server = create_server()
    tools = asyncio.run(server.list_tools())
    tool_names = {tool.name for tool in tools}

    assert "ingest_paper" in tool_names
    assert "get_ingest_status" in tool_names


def test_ingest_paper_output_schema_returns_job_id_and_queued_status() -> None:
    result = handle_ingest_paper(
        url="https://example.com/papers/sample.pdf",
        pipeline=StubPipeline(),
    )

    assert "job_id" in result
    assert result["paper_id"] is None
    assert result["status"] == "queued"
    assert "message" in result


def test_ingest_paper_output_schema_returns_paper_id_when_skipped() -> None:
    result = handle_ingest_paper(
        url="https://example.com/papers/sample.pdf",
        pipeline=SkippingPipeline(),
    )

    assert "job_id" in result
    assert result["status"] == "skipped"
    assert result["paper_id"] == "paper-456"


def test_tool_error_format_for_invalid_ingest_url() -> None:
    result = handle_ingest_paper(url="not-a-valid-url")

    assert result["error"] is True
    assert result["error_code"] == "INGEST_INVALID_URL"
    assert "error_message" in result
    assert "retryable" in result
