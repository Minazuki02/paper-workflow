"""Quality baseline for Phase 1 metadata extraction and section structuring."""

from __future__ import annotations

import sys
from pathlib import Path

import fitz

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.common.config import AppConfig
from backend.ingest.parser import parse_pdf
from backend.ingest.structurer import structure_parse_result
from backend.storage.file_store import PdfFileStore


def test_structurer_extracts_baseline_metadata_and_key_sections(tmp_path: Path) -> None:
    file_store = PdfFileStore(settings=_settings_for(tmp_path))
    pdf_path = _store_benchmark_pdf(file_store)

    parse_result = parse_pdf(pdf_path, paper_id="paper-quality-1", file_store=file_store)
    structured = structure_parse_result(
        parse_result,
        source_url="https://example.com/paper",
        source_pdf_url="https://example.com/paper.pdf",
    )

    assert structured.paper.title == "Adaptive Agent Planning for Literature Review"
    assert [author.name for author in structured.paper.authors] == ["Alice Smith", "Bob Jones"]
    assert structured.paper.abstract.startswith("We present a lightweight planning workflow")
    assert structured.paper.year == 2024
    assert structured.paper.section_count >= 5

    headings = [section.heading for section in structured.sections]
    section_types = {section.section_type for section in structured.sections}

    assert "Abstract" in headings
    assert "1 Introduction" in headings
    assert "3 Methodology" in headings
    assert "4 Experiments" in headings
    assert {"abstract", "introduction", "methodology", "experiments", "conclusion"} <= section_types


def test_boilerplate_copyright_does_not_pollute_title(tmp_path: Path) -> None:
    """Simulate the Attention Is All You Need PDF layout: copyright notice before title."""
    file_store = PdfFileStore(settings=_settings_for(tmp_path))
    pdf_path = _store_boilerplate_pdf(file_store)

    parse_result = parse_pdf(pdf_path, paper_id="paper-quality-bp", file_store=file_store)
    structured = structure_parse_result(
        parse_result,
        source_url="https://arxiv.org/abs/1706.03762",
    )

    assert "Attention" in structured.paper.title
    assert "permission" not in structured.paper.title.lower()
    assert "scholarly" not in structured.paper.title.lower()
    # Section count should be reasonable (not ~98 from prose false-positives).
    assert structured.paper.section_count <= 20, (
        f"Too many sections: {structured.paper.section_count}"
    )


def _store_boilerplate_pdf(file_store: PdfFileStore) -> str:
    """Create a PDF mimicking arXiv copyright-notice + numbered-heading layout."""
    page_one_text = "\n".join([
        "Provided proper attribution is provided, Google hereby grants permission to",
        "reproduce the tables and figures in this paper solely for use in",
        "journalistic or scholarly works.",
        "",
        "Attention Is All You Need",
        "",
        "Ashish Vaswani, Noam Shazeer, Niki Parmar",
        "",
        "Abstract",
        "The dominant sequence transduction models are based on complex recurrent",
        "or convolutional neural networks that include an encoder and a decoder.",
        "",
        "1 Introduction",
        "Recurrent neural networks, long short-term memory and gated recurrent",
        "neural networks in particular, have been firmly established as state of the",
        "art approaches in sequence modeling and transduction problems.",
    ])
    page_two_text = "\n".join([
        "2 Background",
        "The goal of reducing sequential computation also forms the foundation of the",
        "Extended Neural GPU, ByteNet, and ConvS2S, all of which use convolutional",
        "neural networks as basic building block.",
        "3 Model Architecture",
        "Most competitive neural sequence transduction models have an encoder-decoder",
        "structure. Here, the encoder maps an input sequence of symbol representations.",
        "3.1 Encoder and Decoder Stacks",
        "The encoder is composed of a stack of six identical layers.",
        "4 Experiments",
        "We evaluate the Transformer on machine translation benchmarks.",
        "5 Conclusion",
        "We presented the Transformer, the first sequence transduction model based",
        "entirely on attention.",
        "References",
        "Vaswani et al. Attention Is All You Need. NeurIPS 2017.",
    ])

    document = fitz.open()
    for text in (page_one_text, page_two_text):
        page = document.new_page()
        page.insert_textbox((72, 72, 520, 760), text, fontsize=10)

    pdf_bytes = document.tobytes()
    document.close()
    relative_path, _, _ = file_store.save_bytes(pdf_bytes)
    return relative_path


def _store_benchmark_pdf(file_store: PdfFileStore) -> str:
    page_one_text = "\n".join(
        [
            "Adaptive Agent Planning for Literature Review",
            "Alice Smith, Bob Jones",
            "2024",
            "Abstract",
            "We present a lightweight planning workflow for ingesting academic papers.",
            "The system structures metadata before retrieval and analysis.",
            "1 Introduction",
            "Literature review assistants need reliable paper structure to ground later steps.",
            "2 Related Work",
            "Prior systems often rely on brittle rule sets or external services.",
        ]
    )
    page_two_text = "\n".join(
        [
            "3 Methodology",
            "Our pipeline extracts title, author, abstract, and major section boundaries.",
            "4 Experiments",
            "We evaluate extraction quality on representative benchmark PDFs.",
            "5 Conclusion",
            "Structured parsing is sufficient for the Phase 1 ingest workflow.",
        ]
    )

    document = fitz.open()
    for text in (page_one_text, page_two_text):
        page = document.new_page()
        page.insert_textbox((72, 72, 520, 760), text, fontsize=12)

    pdf_bytes = document.tobytes()
    document.close()
    relative_path, _, _ = file_store.save_bytes(pdf_bytes)
    return relative_path


def _settings_for(tmp_path: Path) -> AppConfig:
    return AppConfig.model_validate(
        {
            "app": {"name": "paper-workflow-test"},
            "paths": {
                "data_dir": tmp_path / "data",
                "logs_dir": tmp_path / "data" / "logs",
                "db_path": tmp_path / "data" / "db" / "papers.db",
                "index_dir": tmp_path / "data" / "index",
                "pdf_dir": tmp_path / "data" / "pdfs",
            },
            "models": {"embedding_model": "all-MiniLM-L6-v2"},
            "logging": {"level": "INFO", "json": True},
        }
    )
