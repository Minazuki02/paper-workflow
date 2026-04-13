"""Unit tests for retrieval metadata filters."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.common.db import initialize_database
from backend.common.models import Author, Chunk, Paper
from backend.retrieval.filters import RetrievalFilters, count_ready_chunks, fetch_chunk_records
from backend.storage.sqlite_store import SQLiteMetadataStore


def test_fetch_chunk_records_applies_year_and_section_filters() -> None:
    store = SQLiteMetadataStore(connection=initialize_database(db_path=":memory:"))
    _seed_records(store)

    records = fetch_chunk_records(
        store.connection,
        filters=RetrievalFilters(
            year_from=2024,
            section_types=("methodology",),
        ),
    )

    assert [record.chunk_id for record in records] == ["chunk-method-2024"]
    assert records[0].paper_title == "Agent Planning in Practice"
    assert records[0].authors == "Alice Smith, Bob Jones"


def test_count_ready_chunks_respects_paper_filters() -> None:
    store = SQLiteMetadataStore(connection=initialize_database(db_path=":memory:"))
    papers = _seed_records(store)

    chunk_count = count_ready_chunks(
        store.connection,
        filters=RetrievalFilters(paper_ids=(papers["paper-2023"].paper_id,)),
    )

    assert chunk_count == 1


def _seed_records(store: SQLiteMetadataStore) -> dict[str, Paper]:
    paper_2024 = store.upsert_paper(
        Paper(
            paper_id="paper-2024",
            title="Agent Planning in Practice",
            authors=[Author(name="Alice Smith"), Author(name="Bob Jones")],
            year=2024,
            status="ready",
        )
    )
    paper_2023 = store.upsert_paper(
        Paper(
            paper_id="paper-2023",
            title="Attention Benchmarks",
            authors=[Author(name="Carol Lee")],
            year=2023,
            status="ready",
        )
    )

    store.replace_chunks(
        paper_2024.paper_id,
        [
            Chunk(
                chunk_id="chunk-method-2024",
                paper_id=paper_2024.paper_id,
                text="We study adaptive agent planning with hierarchical search.",
                char_count=64,
                order_index=0,
                page_start=2,
                section_type="methodology",
                heading="2 Methodology",
            ),
            Chunk(
                chunk_id="chunk-exp-2024",
                paper_id=paper_2024.paper_id,
                text="Experiments show improved traceability and stability.",
                char_count=55,
                order_index=1,
                page_start=4,
                section_type="experiments",
                heading="3 Experiments",
            ),
        ],
    )
    store.replace_chunks(
        paper_2023.paper_id,
        [
            Chunk(
                chunk_id="chunk-method-2023",
                paper_id=paper_2023.paper_id,
                text="Baseline attention mechanisms remain competitive.",
                char_count=50,
                order_index=0,
                page_start=3,
                section_type="methodology",
                heading="2 Methods",
            )
        ],
    )
    return {"paper-2024": paper_2024, "paper-2023": paper_2023}
