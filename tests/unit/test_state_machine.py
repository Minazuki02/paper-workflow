"""Unit tests for the paper ingest state machine."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.ingest.state_machine import (
    PAPER_STATUSES,
    InvalidPaperStatusTransition,
    get_allowed_transitions,
    is_valid_transition,
    validate_transition,
)

VALID_TRANSITIONS = {
    ("discovered", "queued"),
    ("queued", "downloading"),
    ("downloading", "downloaded"),
    ("downloading", "failed"),
    ("downloaded", "parsing"),
    ("parsing", "parsed"),
    ("parsing", "failed"),
    ("parsed", "chunked"),
    ("chunked", "embedding"),
    ("embedding", "indexed"),
    ("embedding", "failed"),
    ("indexed", "ready"),
    ("indexed", "failed"),
    ("failed", "queued"),
    ("ready", "archived"),
    ("ready", "queued"),
    ("archived", "queued"),
}

INVALID_TRANSITIONS = {
    ("discovered", "ready"),
    ("downloading", "ready"),
    ("parsing", "indexed"),
    ("ready", "downloading"),
    ("archived", "ready"),
}


@pytest.mark.parametrize(("from_status", "to_status"), sorted(VALID_TRANSITIONS))
def test_documented_valid_transitions(from_status: str, to_status: str) -> None:
    assert is_valid_transition(from_status, to_status) is True
    validate_transition(from_status, to_status)


@pytest.mark.parametrize(("from_status", "to_status"), sorted(INVALID_TRANSITIONS))
def test_documented_invalid_transitions(from_status: str, to_status: str) -> None:
    assert is_valid_transition(from_status, to_status) is False
    with pytest.raises(InvalidPaperStatusTransition):
        validate_transition(from_status, to_status)


def test_only_documented_transitions_are_allowed() -> None:
    for from_status in PAPER_STATUSES:
        for to_status in PAPER_STATUSES:
            expected = (from_status, to_status) in VALID_TRANSITIONS
            assert is_valid_transition(from_status, to_status) is expected


def test_retry_from_failed_only_returns_to_queue() -> None:
    assert get_allowed_transitions("failed") == frozenset({"queued"})


def test_invalid_transition_error_lists_allowed_targets() -> None:
    with pytest.raises(InvalidPaperStatusTransition) as exc_info:
        validate_transition("downloaded", "ready")

    error = exc_info.value
    assert error.from_status == "downloaded"
    assert error.to_status == "ready"
    assert error.allowed_targets == frozenset({"parsing"})
    assert "downloaded -> ready" in str(error)
    assert "parsing" in str(error)
