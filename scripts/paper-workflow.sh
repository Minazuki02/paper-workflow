#!/usr/bin/env bash
set -euo pipefail

# ──────────────────────────────────────────────────────────
# Paper Workflow — Enable / Disable / Status
#
# Quickly toggle paper workflow without full uninstall.
# Data and Python package are always preserved.
#
# Usage:
#   bash scripts/paper-workflow.sh enable
#   bash scripts/paper-workflow.sh disable
#   bash scripts/paper-workflow.sh status
# ──────────────────────────────────────────────────────────

CLAUDE_HOME="${CLAUDE_HOME:-$HOME/.claude}"
MANIFEST="$CLAUDE_HOME/.paper-workflow-manifest.json"
MANIFEST_OFF="$CLAUDE_HOME/.paper-workflow-manifest.json.disabled"
PYTHON="${PYTHON:-python3}"

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[0;33m'
CYAN='\033[0;36m'
NC='\033[0m'

MARKER_START="<!-- paper-workflow:start -->"
MARKER_END="<!-- paper-workflow:end -->"

# ── Helpers ─────────────────────────────────────────────

is_installed() {
    [ -f "$MANIFEST" ] || [ -f "$MANIFEST_OFF" ]
}

is_enabled() {
    [ -f "$MANIFEST" ]
}

# ── disable ─────────────────────────────────────────────

do_disable() {
    if ! is_installed; then
        echo -e "${RED}✗${NC} Paper Workflow is not installed."
        echo "  Run: bash scripts/install.sh"
        exit 1
    fi

    if ! is_enabled; then
        echo -e "${YELLOW}!${NC} Already disabled."
        exit 0
    fi

    echo "Disabling Paper Workflow..."

    # Read manifest to know what files to move
    $PYTHON - "$MANIFEST" "$CLAUDE_HOME" << 'PYEOF'
import json, sys, os

manifest_path = sys.argv[1]
claude_home = sys.argv[2]

with open(manifest_path) as f:
    manifest = json.load(f)

for rel_path in manifest.get("files", []):
    src = os.path.join(claude_home, rel_path)
    dst = src + ".disabled"
    if os.path.exists(src):
        os.rename(src, dst)
PYEOF

    # Hide CLAUDE.md block by commenting markers
    CLAUDE_MD="$CLAUDE_HOME/CLAUDE.md"
    if [ -f "$CLAUDE_MD" ] && grep -q "$MARKER_START" "$CLAUDE_MD"; then
        $PYTHON - "$CLAUDE_MD" "$MARKER_START" "$MARKER_END" << 'PYEOF'
import sys, re

path, start, end = sys.argv[1], sys.argv[2], sys.argv[3]
with open(path) as f:
    content = f.read()

# Replace block with a disabled marker (preserves content for re-enable)
pattern = re.escape(start) + r'(.*?)' + re.escape(end)
disabled_start = start.replace("-->", " disabled -->")
disabled_end = end.replace("<!--", "<!-- disabled")
content = re.sub(pattern, disabled_start + r'\1' + disabled_end, content, flags=re.DOTALL)

with open(path, "w") as f:
    f.write(content)
PYEOF
    fi

    # Remove MCP servers from settings.json
    export CLAUDE_HOME
    $PYTHON - "$MANIFEST" << 'PYEOF'
import json, sys, os

claude_home = os.environ.get("CLAUDE_HOME", os.path.expanduser("~/.claude"))
manifest_path = sys.argv[1]
settings_path = os.path.join(claude_home, "settings.json")

if not os.path.exists(settings_path):
    sys.exit(0)

with open(manifest_path) as f:
    manifest = json.load(f)
with open(settings_path) as f:
    settings = json.load(f)

# Remove MCP servers
for name in manifest.get("mcp_servers", []):
    settings.get("mcpServers", {}).pop(name, None)
if not settings.get("mcpServers"):
    settings.pop("mcpServers", None)

# Remove permissions
for perm in manifest.get("permissions", []):
    try:
        settings.get("permissions", {}).get("allow", []).remove(perm)
    except ValueError:
        pass
if not settings.get("permissions", {}).get("allow"):
    settings.get("permissions", {}).pop("allow", None)
if not settings.get("permissions"):
    settings.pop("permissions", None)

# Remove paper hooks
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

if settings:
    with open(settings_path, "w") as f:
        json.dump(settings, f, indent=2, ensure_ascii=False)
        f.write("\n")
else:
    os.remove(settings_path)
PYEOF

    # Mark manifest as disabled
    mv "$MANIFEST" "$MANIFEST_OFF"

    echo -e "${GREEN}✓${NC} Paper Workflow disabled."
    echo "  Claude Code is now in pure coding mode."
    echo "  Re-enable: bash scripts/paper-workflow.sh enable"
}

# ── enable ──────────────────────────────────────────────

do_enable() {
    if ! is_installed; then
        echo -e "${RED}✗${NC} Paper Workflow is not installed."
        echo "  Run: bash scripts/install.sh"
        exit 1
    fi

    if is_enabled; then
        echo -e "${YELLOW}!${NC} Already enabled."
        exit 0
    fi

    echo "Enabling Paper Workflow..."

    # Restore manifest first
    mv "$MANIFEST_OFF" "$MANIFEST"

    # Restore files
    $PYTHON - "$MANIFEST" "$CLAUDE_HOME" << 'PYEOF'
import json, sys, os

manifest_path = sys.argv[1]
claude_home = sys.argv[2]

with open(manifest_path) as f:
    manifest = json.load(f)

for rel_path in manifest.get("files", []):
    dst = os.path.join(claude_home, rel_path)
    src = dst + ".disabled"
    if os.path.exists(src):
        os.rename(src, dst)
PYEOF

    # Restore CLAUDE.md block
    CLAUDE_MD="$CLAUDE_HOME/CLAUDE.md"
    if [ -f "$CLAUDE_MD" ]; then
        $PYTHON - "$CLAUDE_MD" << 'PYEOF'
import sys
path = sys.argv[1]
with open(path) as f:
    content = f.read()
content = content.replace(" disabled -->", " -->")
content = content.replace("<!-- disabled ", "<!-- ")
with open(path, "w") as f:
    f.write(content)
PYEOF
    fi

    # Re-merge MCP servers into settings.json
    export CLAUDE_HOME
    $PYTHON - "$MANIFEST" << 'PYEOF'
import json, sys, os

claude_home = os.environ.get("CLAUDE_HOME", os.path.expanduser("~/.claude"))
manifest_path = sys.argv[1]
settings_path = os.path.join(claude_home, "settings.json")

with open(manifest_path) as f:
    manifest = json.load(f)

if os.path.exists(settings_path):
    with open(settings_path) as f:
        settings = json.load(f)
else:
    settings = {}

project_root = manifest["project_root"]
project_settings_path = os.path.join(project_root, ".claude", "settings.json")
with open(project_settings_path) as f:
    project_settings = json.load(f)

# Re-add MCP servers
settings.setdefault("mcpServers", {})
for name, config in project_settings.get("mcpServers", {}).items():
    if config.get("cwd") == ".":
        config["cwd"] = project_root
    settings["mcpServers"][name] = config

# Re-add permissions
settings.setdefault("permissions", {})
settings["permissions"].setdefault("allow", [])
for perm in manifest.get("permissions", []):
    if perm not in settings["permissions"]["allow"]:
        settings["permissions"]["allow"].append(perm)

# Re-add hooks
for event, hooks in project_settings.get("hooks", {}).items():
    settings.setdefault("hooks", {}).setdefault(event, [])
    existing_prompts = {h.get("prompt", "") for h in settings["hooks"][event]}
    for hook in hooks:
        if hook.get("prompt", "") not in existing_prompts:
            settings["hooks"][event].append(hook)

with open(settings_path, "w") as f:
    json.dump(settings, f, indent=2, ensure_ascii=False)
    f.write("\n")
PYEOF

    echo -e "${GREEN}✓${NC} Paper Workflow enabled."
    echo "  Paper skills are now available in Claude Code."
}

# ── status ──────────────────────────────────────────────

do_status() {
    if ! is_installed; then
        echo -e "${CYAN}Paper Workflow:${NC} not installed"
        echo "  Run: bash scripts/install.sh"
        return
    fi

    if is_enabled; then
        echo -e "${CYAN}Paper Workflow:${NC} ${GREEN}enabled${NC}"
    else
        echo -e "${CYAN}Paper Workflow:${NC} ${RED}disabled${NC}"
    fi

    # Show manifest info
    local mf="$MANIFEST"
    [ -f "$mf" ] || mf="$MANIFEST_OFF"

    $PYTHON - "$mf" << 'PYEOF'
import json, sys
with open(sys.argv[1]) as f:
    m = json.load(f)
print(f"  Version:     {m.get('version', '?')}")
print(f"  Installed:   {m.get('installed_at', '?')[:19]}")
print(f"  Project:     {m.get('project_root', '?')}")
print(f"  Skills:      {sum(1 for f in m.get('files',[]) if f.startswith('skills/'))}")
print(f"  Agents:      {sum(1 for f in m.get('files',[]) if f.startswith('agents/'))}")
print(f"  Rules:       {sum(1 for f in m.get('files',[]) if f.startswith('rules/'))}")
print(f"  MCP Servers: {len(m.get('mcp_servers',[]))}")
PYEOF
}

# ── Main ────────────────────────────────────────────────

case "${1:-}" in
    enable)  do_enable ;;
    disable) do_disable ;;
    status)  do_status ;;
    *)
        echo "Usage: bash scripts/paper-workflow.sh {enable|disable|status}"
        echo ""
        echo "  enable   — Activate paper workflow in Claude Code"
        echo "  disable  — Deactivate (preserves data, instant re-enable)"
        echo "  status   — Show current state"
        exit 1
        ;;
esac
