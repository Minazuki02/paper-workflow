#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python}"
RUNTIME_DIR="${PAPER_WORKFLOW_SERVER_RUNTIME_DIR:-$(mktemp -d "${TMPDIR:-/tmp}/paper-workflow-servers.XXXXXX")}"
DATA_DIR="${PAPER_WORKFLOW_DATA_DIR:-$RUNTIME_DIR/data}"

mkdir -p "$RUNTIME_DIR"

cleanup() {
  if [[ -n "${INGEST_PID:-}" ]]; then
    kill "$INGEST_PID" >/dev/null 2>&1 || true
  fi
  if [[ -n "${RETRIEVAL_PID:-}" ]]; then
    kill "$RETRIEVAL_PID" >/dev/null 2>&1 || true
  fi
}

trap cleanup EXIT INT TERM

start_server() {
  local name="$1"
  local module="$2"
  local stdout_log="$RUNTIME_DIR/${name}.stdout.log"
  local stderr_log="$RUNTIME_DIR/${name}.stderr.log"

  tail -f /dev/null | env \
    PAPER_WORKFLOW_DATA_DIR="$DATA_DIR" \
    PAPER_WORKFLOW_LOGS_DIR="$DATA_DIR/logs" \
    PAPER_WORKFLOW_DB_PATH="$DATA_DIR/db/papers.db" \
    PAPER_WORKFLOW_INDEX_DIR="$DATA_DIR/index" \
    PAPER_WORKFLOW_PDF_DIR="$DATA_DIR/pdfs" \
    "$PYTHON_BIN" -m "$module" >"$stdout_log" 2>"$stderr_log" &

  local pid="$!"
  printf '%s\n' "$pid" >"$RUNTIME_DIR/${name}.pid"
  printf 'started %-10s pid=%s logs=%s\n' "$name" "$pid" "$stderr_log"
}

cd "$ROOT_DIR"

echo "runtime_dir=$RUNTIME_DIR"
echo "data_dir=$DATA_DIR"

start_server "ingest" "backend.ingest.mcp_server"
INGEST_PID="$(cat "$RUNTIME_DIR/ingest.pid")"

start_server "retrieval" "backend.retrieval.mcp_server"
RETRIEVAL_PID="$(cat "$RUNTIME_DIR/retrieval.pid")"

echo "Use 'python scripts/health_check.py' to verify MCP stdio availability."
echo "Press Ctrl-C to stop both servers."

wait "$INGEST_PID" "$RETRIEVAL_PID"
