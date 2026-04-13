#!/usr/bin/env python3
"""Local availability checks for the Phase 1 MCP stdio servers."""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from time import perf_counter

import anyio
from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

PROJECT_ROOT = Path(__file__).resolve().parents[1]

SERVER_SPECS = {
    "ingest": {
        "server_name": "paper-ingest",
        "module": "backend.ingest.mcp_server",
        "expected_tools": [
            "search_papers",
            "fetch_pdf",
            "ingest_paper",
            "get_ingest_status",
            "batch_ingest",
        ],
    },
    "retrieval": {
        "server_name": "paper-retrieval",
        "module": "backend.retrieval.mcp_server",
        "expected_tools": ["retrieve_evidence"],
    },
}


@dataclass
class HealthCheckResult:
    server_key: str
    server_name: str
    ok: bool
    tools: list[str]
    duration_ms: int
    error: str | None = None


async def _check_server(
    server_key: str,
    *,
    cwd: Path,
    data_dir: Path,
    timeout_seconds: float,
) -> HealthCheckResult:
    spec = SERVER_SPECS[server_key]
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", spec["module"]],
        cwd=str(cwd),
        env=_server_env(data_dir),
    )

    started_at = perf_counter()

    try:
        with anyio.fail_after(timeout_seconds):
            async with stdio_client(params) as (read_stream, write_stream):
                async with ClientSession(read_stream, write_stream) as session:
                    initialize_result = await session.initialize()
                    tools_result = await session.list_tools()
    except Exception as exc:
        return HealthCheckResult(
            server_key=server_key,
            server_name=spec["server_name"],
            ok=False,
            tools=[],
            duration_ms=_elapsed_ms(started_at),
            error=f"{type(exc).__name__}: {exc}",
        )

    tool_names = sorted(tool.name for tool in tools_result.tools)
    server_name = initialize_result.serverInfo.name
    expected_tools = sorted(spec["expected_tools"])
    ok = server_name == spec["server_name"] and tool_names == expected_tools

    return HealthCheckResult(
        server_key=server_key,
        server_name=server_name,
        ok=ok,
        tools=tool_names,
        duration_ms=_elapsed_ms(started_at),
        error=None if ok else _mismatch_error(spec["server_name"], expected_tools, server_name, tool_names),
    )


async def _run_checks(
    server_keys: list[str],
    *,
    cwd: Path,
    data_dir: Path,
    timeout_seconds: float,
) -> list[HealthCheckResult]:
    results: list[HealthCheckResult] = []
    for server_key in server_keys:
        results.append(
            await _check_server(
                server_key,
                cwd=cwd,
                data_dir=data_dir,
                timeout_seconds=timeout_seconds,
            )
        )
    return results


async def _run_checks_entrypoint(
    server_keys: list[str],
    cwd: str,
    data_dir: str,
    timeout_seconds: float,
) -> list[HealthCheckResult]:
    return await _run_checks(
        server_keys,
        cwd=Path(cwd),
        data_dir=Path(data_dir),
        timeout_seconds=timeout_seconds,
    )


def _server_env(data_dir: Path) -> dict[str, str]:
    return {
        **os.environ,
        "PAPER_WORKFLOW_DATA_DIR": str(data_dir),
        "PAPER_WORKFLOW_LOGS_DIR": str(data_dir / "logs"),
        "PAPER_WORKFLOW_DB_PATH": str(data_dir / "db" / "papers.db"),
        "PAPER_WORKFLOW_INDEX_DIR": str(data_dir / "index"),
        "PAPER_WORKFLOW_PDF_DIR": str(data_dir / "pdfs"),
    }


def _elapsed_ms(started_at: float) -> int:
    return max(0, int(round((perf_counter() - started_at) * 1000)))


def _mismatch_error(
    expected_server_name: str,
    expected_tools: list[str],
    actual_server_name: str,
    actual_tools: list[str],
) -> str:
    return (
        f"expected server={expected_server_name} tools={expected_tools}, "
        f"got server={actual_server_name} tools={actual_tools}"
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--server",
        choices=["all", *SERVER_SPECS.keys()],
        default="all",
        help="Choose which server to check.",
    )
    parser.add_argument(
        "--cwd",
        type=Path,
        default=PROJECT_ROOT,
        help="Project root used when spawning the MCP server modules.",
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=None,
        help="Override the runtime data directory used during the health check.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=10.0,
        help="Per-server timeout in seconds.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print machine-readable JSON output.",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    selected_servers = list(SERVER_SPECS) if args.server == "all" else [args.server]
    runtime_root = args.data_dir or Path(tempfile.mkdtemp(prefix="paper-workflow-health-")) / "data"

    results = anyio.run(
        _run_checks_entrypoint,
        selected_servers,
        str(args.cwd.resolve()),
        str(runtime_root.resolve()),
        args.timeout,
    )

    if args.json:
        print(json.dumps([asdict(result) for result in results], ensure_ascii=True, indent=2))
    else:
        for result in results:
            status = "ok" if result.ok else "failed"
            print(
                f"[{status}] {result.server_key} server={result.server_name} "
                f"tools={','.join(result.tools)} duration_ms={result.duration_ms}"
            )
            if result.error:
                print(f"  error: {result.error}")

    return 0 if all(result.ok for result in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
