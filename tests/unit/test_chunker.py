"""Unit tests for the Phase 1 fixed-parameter chunker."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.common.models import Section
from backend.ingest.chunker import CHUNK_TOKEN_OVERLAP, CHUNK_TOKEN_SIZE, chunk_sections


def test_chunker_splits_long_sections_with_fixed_overlap() -> None:
    tokens = [f"token{i}" for i in range(1200)]
    section = Section(
        paper_id="paper-1",
        section_id="section-1",
        heading="3 Methodology",
        section_type="methodology",
        level=1,
        order_index=0,
        text=" ".join(tokens),
        char_count=len(" ".join(tokens)),
    )

    chunks = chunk_sections([section])

    assert len(chunks) == 3
    assert [chunk.order_index for chunk in chunks] == [0, 1, 2]
    assert [chunk.token_count for chunk in chunks] == [512, 512, 432]
    assert chunks[0].section_id == "section-1"
    assert chunks[0].section_type == "methodology"
    assert chunks[0].heading == "3 Methodology"

    first_tokens = chunks[0].text.split()
    second_tokens = chunks[1].text.split()
    third_tokens = chunks[2].text.split()

    assert first_tokens[-CHUNK_TOKEN_OVERLAP:] == second_tokens[:CHUNK_TOKEN_OVERLAP]
    assert second_tokens[-CHUNK_TOKEN_OVERLAP:] == third_tokens[:CHUNK_TOKEN_OVERLAP]


def test_chunker_keeps_single_chunk_at_exact_window_boundary() -> None:
    section = Section(
        paper_id="paper-1",
        section_id="section-2",
        heading="1 Introduction",
        section_type="introduction",
        level=1,
        order_index=0,
        text=" ".join(f"tok{i}" for i in range(CHUNK_TOKEN_SIZE)),
        char_count=0,
    )

    chunks = chunk_sections([section])

    assert len(chunks) == 1
    assert chunks[0].token_count == CHUNK_TOKEN_SIZE
    assert chunks[0].order_index == 0


def test_chunker_skips_sections_without_tokens() -> None:
    section = Section(
        paper_id="paper-1",
        section_id="section-3",
        heading="Appendix",
        section_type="appendix",
        level=1,
        order_index=0,
        text="   \n   ",
        char_count=0,
    )

    assert chunk_sections([section]) == []
