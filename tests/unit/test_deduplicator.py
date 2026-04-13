"""Unit tests for the Phase 1 paper deduplicator."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.common.db import initialize_database
from backend.common.models import Author, Paper
from backend.ingest.deduplicator import PaperDeduplicator
from backend.storage.sqlite_store import SQLiteMetadataStore


def test_deduplicator_detects_exact_doi_match() -> None:
    store = _make_store()
    store.upsert_paper(
        Paper(
            paper_id="paper-existing",
            title="Attention Is All You Need",
            doi="10.1000/attention",
            authors=[Author(name="Alice")],
        )
    )

    result = PaperDeduplicator(store).find_duplicate(
        Paper(
            paper_id="paper-new",
            title="Different Surface Title",
            doi=" 10.1000/ATTENTION ",
            authors=[Author(name="Bob")],
        )
    )

    assert result.is_duplicate is True
    assert result.match_type == "doi"
    assert result.existing_paper_id == "paper-existing"
    assert result.similarity == 1.0


def test_deduplicator_detects_high_similarity_title_match() -> None:
    store = _make_store()
    store.upsert_paper(
        Paper(
            paper_id="paper-existing",
            title="Retrieval-Augmented Generation for Large Language Models",
            authors=[Author(name="Alice")],
        )
    )

    result = PaperDeduplicator(store).find_duplicate(
        Paper(
            paper_id="paper-new",
            title="Retrieval Augmented Generation for Large Language Models.",
            authors=[Author(name="Bob")],
        )
    )

    assert result.is_duplicate is True
    assert result.match_type == "title"
    assert result.existing_paper_id == "paper-existing"
    assert result.similarity is not None
    assert result.similarity >= 0.92


def test_deduplicator_returns_non_duplicate_when_similarity_is_low() -> None:
    store = _make_store()
    store.upsert_paper(
        Paper(
            paper_id="paper-existing",
            title="Transformers for Vision Tasks",
            authors=[Author(name="Alice")],
        )
    )

    result = PaperDeduplicator(store).find_duplicate(
        Paper(
            paper_id="paper-new",
            title="Diffusion Models for Image Synthesis",
            authors=[Author(name="Bob")],
        )
    )

    assert result.is_duplicate is False
    assert result.match_type is None
    assert result.existing_paper_id is None


def _make_store() -> SQLiteMetadataStore:
    return SQLiteMetadataStore(connection=initialize_database(db_path=":memory:"))
