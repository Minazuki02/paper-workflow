#!/usr/bin/env bash
set -euo pipefail

# ──────────────────────────────────────────────────────────
# Paper Workflow — Uninstall
#
# Cleanly removes everything installed by install.sh.
# Reads the manifest to know exactly what to delete.
# ──────────────────────────────────────────────────────────

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
CLAUDE_HOME="${CLAUDE_HOME:-$HOME/.claude}"
MANIFEST="$CLAUDE_HOME/.paper-workflow-manifest.json"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
CYAN='\033[0;36m'
NC='\033[0m'

info()  { echo -e "${GREEN}✓${NC} $1"; }
warn()  { echo -e "${YELLOW}!${NC} $1"; }
error() { echo -e "${RED}✗${NC} $1"; }

echo "=== Paper Workflow Uninstall ==="
echo ""

# ── Check manifest ──────────────────────────────────────

if [ ! -f "$MANIFEST" ]; then
    error "No installation found (missing $MANIFEST)."
    echo "  Paper Workflow does not appear to be installed."
    exit 1
fi

echo -e "${CYAN}Found installation manifest.${NC}"
echo ""

# ── Remove installed files (skills, agents, rules) ─────

PYTHON="${PYTHON:-python3}"

echo "Removing skills, agents, and rules..."
$PYTHON - "$MANIFEST" "$CLAUDE_HOME" << 'PYEOF'
import json, sys, os

manifest_path = sys.argv[1]
claude_home = sys.argv[2]

with open(manifest_path) as f:
    manifest = json.load(f)

for rel_path in manifest.get("files", []):
    full_path = os.path.join(claude_home, rel_path)
    if os.path.exists(full_path):
        os.remove(full_path)
        print(f"  ✓ Removed {rel_path}")
    else:
        print(f"  - Already gone: {rel_path}")
PYEOF

# ── Remove paper-workflow block from CLAUDE.md ──────────

CLAUDE_MD="$CLAUDE_HOME/CLAUDE.md"
MARKER_START="<!-- paper-workflow:start -->"
MARKER_END="<!-- paper-workflow:end -->"

if [ -f "$CLAUDE_MD" ]; then
    if grep -q "$MARKER_START" "$CLAUDE_MD"; then
        # Use Python for reliable multi-line removal
        $PYTHON - "$CLAUDE_MD" "$MARKER_START" "$MARKER_END" << 'PYEOF'
import sys, re

path, start, end = sys.argv[1], sys.argv[2], sys.argv[3]

with open(path) as f:
    content = f.read()

# Remove the block including markers and surrounding blank lines
pattern = r'\n*' + re.escape(start) + r'.*?' + re.escape(end) + r'\n*'
content = re.sub(pattern, '\n', content, flags=re.DOTALL)
content = content.strip()

if content:
    with open(path, "w") as f:
        f.write(content + "\n")
    print("  ✓ Removed paper-workflow block from CLAUDE.md")
else:
    # CLAUDE.md is now empty — remove it
    import os
    os.remove(path)
    print("  ✓ Removed CLAUDE.md (was only paper-workflow content)")
PYEOF
    else
        info "CLAUDE.md has no paper-workflow block (skipped)"
    fi
else
    info "No CLAUDE.md to clean"
fi

# ── Remove from settings.json ──────────────────────────

echo "Cleaning settings.json..."
export CLAUDE_HOME
$PYTHON - "$MANIFEST" << 'PYEOF'
import json, sys, os

claude_home = os.environ.get("CLAUDE_HOME", os.path.expanduser("~/.claude"))
manifest_path = sys.argv[1]
settings_path = os.path.join(claude_home, "settings.json")

if not os.path.exists(settings_path):
    print("  - No settings.json to clean")
    sys.exit(0)

with open(manifest_path) as f:
    manifest = json.load(f)

with open(settings_path) as f:
    settings = json.load(f)

# Remove MCP servers
for name in manifest.get("mcp_servers", []):
    if name in settings.get("mcpServers", {}):
        del settings["mcpServers"][name]
        print(f"  ✓ Removed MCP server: {name}")

# Remove empty mcpServers
if not settings.get("mcpServers"):
    settings.pop("mcpServers", None)

# Remove permissions
for perm in manifest.get("permissions", []):
    allow_list = settings.get("permissions", {}).get("allow", [])
    if perm in allow_list:
        allow_list.remove(perm)

# Remove empty permissions
if not settings.get("permissions", {}).get("allow"):
    settings.get("permissions", {}).pop("allow", None)
if not settings.get("permissions"):
    settings.pop("permissions", None)

# Remove hooks that match paper-workflow matchers
paper_matchers = {"mcp__paper_ingest__", "mcp__paper_retrieval__"}
for event in list(settings.get("hooks", {}).keys()):
    hooks = settings["hooks"][event]
    settings["hooks"][event] = [
        h for h in hooks
        if not any(h.get("matcher", "").startswith(m) for m in paper_matchers)
    ]
    if not settings["hooks"][event]:
        del settings["hooks"][event]
if not settings.get("hooks"):
    settings.pop("hooks", None)

# Write back or remove if empty
if settings:
    with open(settings_path, "w") as f:
        json.dump(settings, f, indent=2, ensure_ascii=False)
        f.write("\n")
    print("  ✓ settings.json cleaned")
else:
    os.remove(settings_path)
    print("  ✓ Removed settings.json (was only paper-workflow config)")
PYEOF

# ── Ask about data directory ────────────────────────────

echo ""
DATA_DIR="$PROJECT_ROOT/data"
if [ -d "$DATA_DIR" ]; then
    echo -e "${YELLOW}Data directory found:${NC} $DATA_DIR"
    echo "  This contains your ingested papers, database, and search index."
    echo ""
    read -rp "  Delete paper data? [y/N] " DELETE_DATA
    if [[ "$DELETE_DATA" =~ ^[Yy]$ ]]; then
        rm -rf "$DATA_DIR"
        info "Data directory removed"
    else
        info "Data directory preserved"
    fi
fi

# ── Ask about Python package ───────────────────────────

echo ""
read -rp "  Uninstall Python backend package? [y/N] " UNINSTALL_PIP
if [[ "$UNINSTALL_PIP" =~ ^[Yy]$ ]]; then
    $PYTHON -m pip uninstall -y paper-workflow-backend 2>/dev/null && \
        info "Python package uninstalled" || \
        warn "Python package not found (already removed?)"
else
    info "Python package preserved"
fi

# ── Remove manifest ────────────────────────────────────

rm -f "$MANIFEST"
info "Manifest removed"

# ── Done ────────────────────────────────────────────────

echo ""
echo "=== Uninstall complete ==="
echo ""
echo "Paper Workflow has been removed from Claude Code."
echo "Your normal CC workflows are unaffected."
echo ""
echo "To reinstall later:"
echo "  bash $PROJECT_ROOT/scripts/install.sh"
echo ""
