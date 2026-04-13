"""Paper ingest status transition rules."""

from __future__ import annotations

from typing import get_args

from backend.common.models import PaperStatus

PAPER_STATUSES: tuple[PaperStatus, ...] = get_args(PaperStatus)

ALLOWED_TRANSITIONS: dict[PaperStatus, frozenset[PaperStatus]] = {
    "discovered": frozenset({"queued"}),
    "queued": frozenset({"downloading"}),
    "downloading": frozenset({"downloaded", "failed"}),
    "downloaded": frozenset({"parsing"}),
    "parsing": frozenset({"parsed", "failed"}),
    "parsed": frozenset({"chunked"}),
    "chunked": frozenset({"embedding"}),
    "embedding": frozenset({"indexed", "failed"}),
    "indexed": frozenset({"ready", "failed"}),
    "ready": frozenset({"archived", "queued"}),
    "failed": frozenset({"queued"}),
    "archived": frozenset({"queued"}),
}


class InvalidPaperStatusTransition(ValueError):
    """Raised when a paper status transition violates the contract."""

    def __init__(self, from_status: PaperStatus, to_status: PaperStatus) -> None:
        allowed_targets = ", ".join(get_allowed_transitions(from_status)) or "(none)"
        super().__init__(
            f"Invalid paper status transition: {from_status} -> {to_status}. "
            f"Allowed targets: {allowed_targets}."
        )
        self.from_status = from_status
        self.to_status = to_status
        self.allowed_targets = get_allowed_transitions(from_status)


def get_allowed_transitions(from_status: PaperStatus) -> frozenset[PaperStatus]:
    """Return the set of contract-approved target states for a given status."""

    return ALLOWED_TRANSITIONS.get(from_status, frozenset())


def is_valid_transition(from_status: PaperStatus, to_status: PaperStatus) -> bool:
    """Check whether a status move is allowed by the ingest state machine."""

    return to_status in get_allowed_transitions(from_status)


def validate_transition(from_status: PaperStatus, to_status: PaperStatus) -> None:
    """Raise when a requested status transition is not part of the contract."""

    if not is_valid_transition(from_status, to_status):
        raise InvalidPaperStatusTransition(from_status, to_status)
