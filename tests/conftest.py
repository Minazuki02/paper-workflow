"""Shared pytest fixtures for the paper-workflow test suite."""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure the project root is on sys.path so that `backend.*` imports work
# regardless of how pytest is invoked.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))
