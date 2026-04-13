#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "=== Paper Workflow Setup ==="
echo ""

# Check Python version
PYTHON=${PYTHON:-python3}
if ! command -v "$PYTHON" &> /dev/null; then
    echo "Error: $PYTHON not found. Please install Python >= 3.11."
    exit 1
fi

PY_VERSION=$($PYTHON -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
PY_MAJOR=$($PYTHON -c 'import sys; print(sys.version_info.major)')
PY_MINOR=$($PYTHON -c 'import sys; print(sys.version_info.minor)')

if [ "$PY_MAJOR" -lt 3 ] || { [ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -lt 11 ]; }; then
    echo "Error: Python >= 3.11 required, found $PY_VERSION"
    exit 1
fi
echo "✓ Python $PY_VERSION"

# Install backend
echo ""
echo "Installing backend dependencies..."
$PYTHON -m pip install -e "$PROJECT_ROOT/backend" --quiet
echo "✓ Backend installed"

# .env setup
if [ ! -f "$PROJECT_ROOT/.env" ]; then
    cp "$PROJECT_ROOT/.env.example" "$PROJECT_ROOT/.env"
    echo "✓ Created .env from .env.example — edit it with your API keys"
else
    echo "✓ .env already exists"
fi

# Create data directories
mkdir -p "$PROJECT_ROOT/data/pdfs" "$PROJECT_ROOT/data/db" "$PROJECT_ROOT/data/index" "$PROJECT_ROOT/data/cache" "$PROJECT_ROOT/data/logs"
echo "✓ Data directories created"

echo ""
echo "=== Setup complete ==="
echo ""
echo "Next steps:"
echo "  1. Edit .env with your embedding/LLM API configuration"
echo "  2. Run: claude"
echo "  3. Try: /paper-search \"transformer attention\""
