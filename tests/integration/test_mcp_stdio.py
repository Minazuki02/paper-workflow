"""Integration coverage for MCP stdio lifecycle and Phase 1 analyze boundaries."""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

import anyio
import yaml
from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

EXPECTED_INGEST_TOOLS = {
    "search_papers",
    "fetch_pdf",
    "ingest_paper",
    "get_ingest_status",
    "batch_ingest",
}
EXPECTED_RETRIEVAL_TOOLS = {"retrieve_evidence"}
ANALYZE_ALLOWED_TOOLS = {
    "mcp__paper_retrieval__retrieve_evidence",
    "mcp__paper_ingest__get_ingest_status",
    "TodoWrite",
}


def test_ingest_server_supports_stdio_lifecycle_and_structured_errors(tmp_path: Path) -> None:
    result = anyio.run(
        _exercise_server,
        "backend.ingest.mcp_server",
        "paper-ingest",
        EXPECTED_INGEST_TOOLS,
        "get_ingest_status",
        {},
        tmp_path,
    )

    assert result["server_name"] == "paper-ingest"
    assert result["tool_names"] == sorted(EXPECTED_INGEST_TOOLS)
    assert result["call_result"]["structured"]["error"] is True
    assert result["call_result"]["structured"]["error_code"] == "STATUS_NOT_FOUND"
    assert "error_message" in result["call_result"]["structured"]


def test_retrieval_server_supports_stdio_lifecycle_and_structured_errors(tmp_path: Path) -> None:
    result = anyio.run(
        _exercise_server,
        "backend.retrieval.mcp_server",
        "paper-retrieval",
        EXPECTED_RETRIEVAL_TOOLS,
        "retrieve_evidence",
        {"query": "attention mechanism", "search_mode": "text", "top_k": 3},
        tmp_path,
    )

    assert result["server_name"] == "paper-retrieval"
    assert result["tool_names"] == sorted(EXPECTED_RETRIEVAL_TOOLS)
    assert result["call_result"]["structured"]["error"] is True
    assert result["call_result"]["structured"]["error_code"] == "RETRIEVE_EMPTY_INDEX"
    assert result["call_result"]["structured"]["retryable"] is False


def test_paper_analyze_skill_preserves_phase1_analysis_contract() -> None:
    skill_path = PROJECT_ROOT / ".claude" / "skills" / "paper-analyze.md"
    content = skill_path.read_text(encoding="utf-8")
    frontmatter = _load_frontmatter(skill_path)

    assert set(frontmatter["allowedTools"]) == ANALYZE_ALLOWED_TOOLS
    assert "analyze_paper" not in "\n".join(frontmatter["allowedTools"])
    assert "Do not call a nonexistent `analyze_paper` MCP tool." in content

    expected_sections = [
        "`Summary`",
        "`Contributions`",
        "`Methodology`",
        "`Key Findings`",
        "`Limitations`",
    ]
    positions = [content.index(section) for section in expected_sections]
    assert positions == sorted(positions)


async def _exercise_server(
    module: str,
    expected_server_name: str,
    expected_tools: set[str],
    tool_name: str,
    arguments: dict[str, object],
    tmp_path: Path,
) -> dict[str, object]:
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", module],
        cwd=str(PROJECT_ROOT),
        env=_server_env(tmp_path),
    )

    with anyio.fail_after(10):
        async with stdio_client(params) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                initialize_result = await session.initialize()
                tools_result = await session.list_tools()
                call_result = await session.call_tool(tool_name, arguments)

    tool_names = sorted(tool.name for tool in tools_result.tools)
    assert set(tool_names) == expected_tools
    assert initialize_result.serverInfo.name == expected_server_name

    return {
        "server_name": initialize_result.serverInfo.name,
        "tool_names": tool_names,
        "call_result": {
            "is_error": bool(call_result.isError),
            "structured": dict(call_result.structuredContent or {}),
        },
    }


def _server_env(tmp_path: Path) -> dict[str, str]:
    data_dir = tmp_path / "data"
    return {
        **os.environ,
        "PAPER_WORKFLOW_DATA_DIR": str(data_dir),
        "PAPER_WORKFLOW_LOGS_DIR": str(data_dir / "logs"),
        "PAPER_WORKFLOW_DB_PATH": str(data_dir / "db" / "papers.db"),
        "PAPER_WORKFLOW_INDEX_DIR": str(data_dir / "index"),
        "PAPER_WORKFLOW_PDF_DIR": str(data_dir / "pdfs"),
    }


def _load_frontmatter(path: Path) -> dict[str, object]:
    content = path.read_text(encoding="utf-8")
    match = re.match(r"^---\n(.*?)\n---\n", content, flags=re.DOTALL)
    if match is None:
        raise AssertionError(f"Missing frontmatter in {path}")
    payload = yaml.safe_load(match.group(1))
    if not isinstance(payload, dict):
        raise AssertionError(f"Invalid frontmatter payload in {path}")
    return payload
