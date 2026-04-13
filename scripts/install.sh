#!/usr/bin/env bash
set -euo pipefail

# ──────────────────────────────────────────────────────────
# Paper Workflow — Global Install
#
# Installs paper-workflow into ~/.claude/ so Claude Code
# picks it up from any directory. Writes a manifest for
# clean uninstall.
# ──────────────────────────────────────────────────────────

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
CLAUDE_HOME="${CLAUDE_HOME:-$HOME/.claude}"
MANIFEST="$CLAUDE_HOME/.paper-workflow-manifest.json"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
NC='\033[0m'

info()  { echo -e "${GREEN}✓${NC} $1"; }
warn()  { echo -e "${YELLOW}!${NC} $1"; }
error() { echo -e "${RED}✗${NC} $1"; }

echo "=== Paper Workflow Install ==="
echo ""

# ── Pre-checks ──────────────────────────────────────────

# Check for existing installation
if [ -f "$MANIFEST" ]; then
    warn "Paper Workflow is already installed."
    echo "  Run: bash $PROJECT_ROOT/scripts/uninstall.sh"
    echo "  Then re-run this script to reinstall."
    exit 1
fi

# Check Python
PYTHON="${PYTHON:-python3}"
if ! command -v "$PYTHON" &>/dev/null; then
    error "$PYTHON not found. Install Python >= 3.11."
    exit 1
fi

PY_MAJOR=$($PYTHON -c 'import sys; print(sys.version_info.major)')
PY_MINOR=$($PYTHON -c 'import sys; print(sys.version_info.minor)')
if [ "$PY_MAJOR" -lt 3 ] || { [ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -lt 11 ]; }; then
    error "Python >= 3.11 required, found $PY_MAJOR.$PY_MINOR"
    exit 1
fi
info "Python $PY_MAJOR.$PY_MINOR"

# Check Claude Code
if ! command -v claude &>/dev/null; then
    warn "claude CLI not found on PATH. Install Claude Code first:"
    echo "  https://docs.anthropic.com/en/docs/claude-code"
fi

# ── Install Python backend ──────────────────────────────

echo ""
echo "Installing Python backend..."
$PYTHON -m pip install -e "$PROJECT_ROOT/backend" --quiet 2>/dev/null || \
$PYTHON -m pip install -e "$PROJECT_ROOT/backend"
info "Backend installed"

# ── Prepare ~/.claude directories ───────────────────────

mkdir -p "$CLAUDE_HOME/skills" "$CLAUDE_HOME/agents" "$CLAUDE_HOME/rules"

# ── Copy skills ─────────────────────────────────────────

INSTALLED_FILES=()

echo ""
echo "Installing skills..."
for f in "$PROJECT_ROOT/.claude/skills"/paper-*.md; do
    [ -f "$f" ] || continue
    name="$(basename "$f")"
    cp "$f" "$CLAUDE_HOME/skills/$name"
    INSTALLED_FILES+=("skills/$name")
    info "  $name"
done

# ── Copy agents ─────────────────────────────────────────

echo "Installing agents..."
for f in "$PROJECT_ROOT/.claude/agents"/*.md; do
    [ -f "$f" ] || continue
    name="$(basename "$f")"
    [ "$name" = ".gitkeep" ] && continue
    cp "$f" "$CLAUDE_HOME/agents/$name"
    INSTALLED_FILES+=("agents/$name")
    info "  $name"
done

# ── Copy rules ──────────────────────────────────────────

echo "Installing rules..."
for f in "$PROJECT_ROOT/.claude/rules"/paper-*.md; do
    [ -f "$f" ] || continue
    name="$(basename "$f")"
    cp "$f" "$CLAUDE_HOME/rules/$name"
    INSTALLED_FILES+=("rules/$name")
    info "  $name"
done

# ── Inject into CLAUDE.md ──────────────────────────────

echo "Injecting rules into CLAUDE.md..."
CLAUDE_MD="$CLAUDE_HOME/CLAUDE.md"
MARKER_START="<!-- paper-workflow:start -->"
MARKER_END="<!-- paper-workflow:end -->"

PAPER_BLOCK="$MARKER_START
# Paper Workflow Rules

The paper workflow rules activate only when your request involves academic papers, literature, citations, or research evidence.

@rules/paper-routing.md
@rules/paper-output-format.md
@rules/paper-error-handling.md

For non-paper tasks, the default coding-assistant behavior is preserved.
$MARKER_END"

if [ -f "$CLAUDE_MD" ]; then
    # Append if not already present
    if grep -q "$MARKER_START" "$CLAUDE_MD"; then
        warn "CLAUDE.md already has paper-workflow block (skipped)"
    else
        echo "" >> "$CLAUDE_MD"
        echo "$PAPER_BLOCK" >> "$CLAUDE_MD"
        info "Appended to existing CLAUDE.md"
    fi
else
    echo "$PAPER_BLOCK" > "$CLAUDE_MD"
    info "Created CLAUDE.md"
fi

# ── Merge into settings.json ───────────────────────────

echo "Merging MCP servers into settings.json..."

export CLAUDE_HOME PROJECT_ROOT
$PYTHON << 'PYEOF' && info "settings.json updated" || { error "Failed to merge settings.json"; exit 1; }
import json, sys, os

claude_home = os.environ.get("CLAUDE_HOME", os.path.expanduser("~/.claude"))
project_root = os.environ.get("PROJECT_ROOT", ".")
settings_path = os.path.join(claude_home, "settings.json")

if os.path.exists(settings_path):
    with open(settings_path) as f:
        settings = json.load(f)
else:
    settings = {}

project_settings_path = os.path.join(project_root, ".claude", "settings.json")
with open(project_settings_path) as f:
    project_settings = json.load(f)

settings.setdefault("mcpServers", {})
for name, config in project_settings.get("mcpServers", {}).items():
    if config.get("cwd") == ".":
        config["cwd"] = project_root
    settings["mcpServers"][name] = config

settings.setdefault("permissions", {})
settings["permissions"].setdefault("allow", [])
for perm in project_settings.get("permissions", {}).get("allow", []):
    if perm not in settings["permissions"]["allow"]:
        settings["permissions"]["allow"].append(perm)

settings.setdefault("hooks", {})
for event, hooks in project_settings.get("hooks", {}).items():
    settings["hooks"].setdefault(event, [])
    existing_prompts = {h.get("prompt", "") for h in settings["hooks"][event]}
    for hook in hooks:
        if hook.get("prompt", "") not in existing_prompts:
            settings["hooks"][event].append(hook)

with open(settings_path, "w") as f:
    json.dump(settings, f, indent=2, ensure_ascii=False)
    f.write("\n")
PYEOF

# ── Create data directories ────────────────────────────

DATA_DIR="$PROJECT_ROOT/data"
mkdir -p "$DATA_DIR/pdfs" "$DATA_DIR/db" "$DATA_DIR/index" "$DATA_DIR/cache" "$DATA_DIR/logs"
info "Data directories ready"

# ── .env setup ──────────────────────────────────────────

if [ ! -f "$PROJECT_ROOT/.env" ]; then
    if [ -f "$PROJECT_ROOT/.env.example" ]; then
        cp "$PROJECT_ROOT/.env.example" "$PROJECT_ROOT/.env"
        info "Created .env from .env.example — edit it with your API keys"
    fi
else
    info ".env already exists"
fi

# ── Write manifest ──────────────────────────────────────

$PYTHON - "$MANIFEST" "$PROJECT_ROOT" "${INSTALLED_FILES[@]}" << 'PYEOF'
import json, sys
from datetime import datetime, timezone

manifest_path = sys.argv[1]
project_root = sys.argv[2]
files = list(sys.argv[3:])

manifest = {
    "version": "0.1.0",
    "installed_at": datetime.now(timezone.utc).isoformat(),
    "project_root": project_root,
    "files": files,
    "mcp_servers": ["paper-ingest", "paper-retrieval"],
    "permissions": [
        "mcp__paper_ingest__search_papers",
        "mcp__paper_ingest__ingest_paper",
        "mcp__paper_ingest__get_ingest_status",
        "mcp__paper_ingest__fetch_pdf",
        "mcp__paper_retrieval__retrieve_evidence"
    ]
}

with open(manifest_path, "w") as f:
    json.dump(manifest, f, indent=2)
    f.write("\n")
PYEOF

info "Manifest written to $MANIFEST"

# ── Done ────────────────────────────────────────────────

echo ""
echo "=== Install complete ==="
echo ""
echo "Paper Workflow is now available globally in Claude Code."
echo ""
echo "  Start Claude Code from any directory:"
echo "    claude"
echo ""
echo "  Try:"
echo "    /paper-search \"transformer attention\""
echo ""
echo "  To uninstall:"
echo "    bash $PROJECT_ROOT/scripts/uninstall.sh"
echo ""
