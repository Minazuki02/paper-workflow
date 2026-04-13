"""Unit tests for structurer metadata extraction and heading detection."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.ingest.structurer import (
    _extract_title,
    _extract_authors,
    _extract_abstract,
    _looks_like_heading,
    _is_boilerplate_line,
    _skip_leading_boilerplate,
    _clean_lines,
    _build_sections,
    structure_parse_result,
)
from backend.common.models import Author


# ---------------------------------------------------------------------------
# Boilerplate detection
# ---------------------------------------------------------------------------

class TestBoilerplateDetection:
    @pytest.mark.parametrize("line", [
        "Provided proper attribution is provided, Google hereby grants permission to",
        "Copyright 2017 by the authors",
        "Licensed under Creative Commons CC-BY 4.0",
        "arXiv:1706.03762v5 [cs.CL] 6 Dec 2017",
        "Published in Proceedings of NeurIPS 2017",
        "To appear in ICML 2024",
        "Accepted at AAAI 2023",
        "Submitted to Nature Machine Intelligence",
        "All rights reserved.",
        "Under the terms of the MIT License",
        "© 2023 The Authors",
    ])
    def test_boilerplate_lines_detected(self, line: str) -> None:
        assert _is_boilerplate_line(line) is True

    @pytest.mark.parametrize("line", [
        "Attention Is All You Need",
        "Ashish Vaswani, Noam Shazeer, Niki Parmar",
        "Abstract",
        "1 Introduction",
        "We present a novel approach to sequence transduction.",
        "The Transformer model architecture is described in Section 3.",
    ])
    def test_non_boilerplate_lines_not_detected(self, line: str) -> None:
        assert _is_boilerplate_line(line) is False


class TestSkipLeadingBoilerplate:
    def test_skips_copyright_block_before_title(self) -> None:
        lines = [
            "Provided proper attribution is provided, Google hereby grants permission to",
            "reproduce the tables and figures in this paper solely for use in journalistic or",
            "scholarly works.",
            "Attention Is All You Need",
            "Ashish Vaswani, Noam Shazeer",
        ]
        result = _skip_leading_boilerplate(lines)
        assert result[0] == "Attention Is All You Need"

    def test_no_boilerplate_returns_all_lines(self) -> None:
        lines = [
            "Attention Is All You Need",
            "Ashish Vaswani, Noam Shazeer",
            "Abstract",
        ]
        assert _skip_leading_boilerplate(lines) == lines

    def test_skips_arxiv_header(self) -> None:
        lines = [
            "arXiv:1706.03762v5 [cs.CL] 6 Dec 2017",
            "Attention Is All You Need",
        ]
        result = _skip_leading_boilerplate(lines)
        assert result[0] == "Attention Is All You Need"

    def test_skips_multi_line_copyright_with_short_tail(self) -> None:
        lines = [
            "Copyright 2024 The Authors.",
            "Licensed under CC-BY 4.0.",
            "BERT: Pre-training of Deep Bidirectional Transformers",
            "Jacob Devlin, Ming-Wei Chang",
        ]
        result = _skip_leading_boilerplate(lines)
        assert result[0] == "BERT: Pre-training of Deep Bidirectional Transformers"


# ---------------------------------------------------------------------------
# Title extraction
# ---------------------------------------------------------------------------

class TestExtractTitle:
    def test_basic_title(self) -> None:
        lines = _clean_lines(
            "Attention Is All You Need\n"
            "Ashish Vaswani, Noam Shazeer\n"
            "Abstract\n"
        )
        assert _extract_title(lines) == "Attention Is All You Need"

    def test_title_after_copyright_block(self) -> None:
        lines = _clean_lines(
            "Provided proper attribution is provided, Google hereby grants permission to\n"
            "reproduce the tables and figures in this paper solely for use in journalistic or\n"
            "scholarly works.\n"
            "Attention Is All You Need\n"
            "Ashish Vaswani, Noam Shazeer\n"
        )
        title = _extract_title(lines)
        assert "Attention" in title
        assert "permission" not in title.lower()

    def test_title_after_arxiv_header(self) -> None:
        lines = _clean_lines(
            "arXiv:2301.00001v1 [cs.CL] 1 Jan 2023\n"
            "My Great Paper Title\n"
            "Alice Smith, Bob Jones\n"
        )
        assert _extract_title(lines) == "My Great Paper Title"

    def test_multi_line_title(self) -> None:
        # Titles starting with a single letter like "A" are tricky because the
        # numbered-heading pattern matches "A <Title>" (appendix-style).  Use a
        # title that doesn't start with a single uppercase letter.
        lines = _clean_lines(
            "Exploring Very Long Paper Titles That Span\n"
            "Multiple Lines in the PDF\n"
            "Alice Smith\n"
        )
        title = _extract_title(lines)
        assert "Very Long Paper Title" in title
        assert "Multiple Lines" in title

    def test_empty_lines_returns_untitled(self) -> None:
        assert _extract_title([]) == "Untitled Paper"


# ---------------------------------------------------------------------------
# Author extraction
# ---------------------------------------------------------------------------

class TestExtractAuthors:
    def test_comma_separated_authors(self) -> None:
        lines = _clean_lines(
            "A Good Paper\n"
            "Alice Smith, Bob Jones, Charlie Brown\n"
            "Abstract\n"
        )
        authors = _extract_authors(lines, "A Good Paper")
        names = [a.name for a in authors]
        assert "Alice Smith" in names
        assert "Bob Jones" in names

    def test_authors_with_unicode_superscripts(self) -> None:
        lines = _clean_lines(
            "Great Paper Title\n"
            "Alice Smith∗, Bob Jones†\n"
            "Abstract\n"
        )
        authors = _extract_authors(lines, "Great Paper Title")
        names = [a.name for a in authors]
        assert "Alice Smith" in names or any("Alice" in n for n in names)

    def test_no_authors_found_returns_empty(self) -> None:
        lines = _clean_lines("Title Only\nAbstract\nSome content here.\n")
        authors = _extract_authors(lines, "Title Only")
        assert authors == []


# ---------------------------------------------------------------------------
# Heading detection
# ---------------------------------------------------------------------------

class TestLooksLikeHeading:
    @pytest.mark.parametrize("line", [
        "Abstract",
        "References",
        "Bibliography",
        "Appendix A",
        "1 Introduction",
        "2.1 Problem Statement",
        "3 Methodology",
        "4 Experiments",
        "5.2 Results",
        "A Data Collection",
    ])
    def test_real_headings_detected(self, line: str) -> None:
        assert _looks_like_heading(line) is True, f"Expected heading: {line!r}"

    @pytest.mark.parametrize("line", [
        # Normal prose that contains heading keywords — should NOT match.
        "our model achieves state of the art results on several benchmarks.",
        "performing models also connect the encoder and decoder through an attention",
        "entirely. Experiments on two machine translation tasks show these models to",
        "the effort to evaluate this idea. Ashish, with Illia, designed and implemented t",
        "implementing tensor2tensor, replacing our earlier codebase, greatly improving re",
        # Lowercase start
        "method for extracting features from raw text",
        "discussion of the limitations of this approach",
        # Too long for an unnumbered heading
        "The Transformer model architecture relies on self-attention mechanisms instead of recurrence",
    ])
    def test_prose_lines_not_detected_as_headings(self, line: str) -> None:
        assert _looks_like_heading(line) is False, f"False positive heading: {line!r}"

    def test_numbered_heading_with_unrecognised_title(self) -> None:
        # "3.2 Why Self-Attention" contains no keyword but is numbered.
        assert _looks_like_heading("3.2 Why Self-Attention") is True

    def test_numbered_heading_with_long_title_rejected(self) -> None:
        # If the "title" portion is sentence-length, reject.
        long_title = "3 " + " ".join(f"word{i}" for i in range(10))
        assert _looks_like_heading(long_title) is False


# ---------------------------------------------------------------------------
# Section building — integration-level check
# ---------------------------------------------------------------------------

class TestBuildSections:
    def test_section_count_for_standard_paper(self) -> None:
        """A paper with numbered headings should produce a reasonable number of sections."""
        text = "\n".join([
            "Abstract",
            "We present a novel model for sequence transduction.",
            "1 Introduction",
            "Sequence to sequence models have been widely adopted.",
            "Recurrent models typically factor computation along positions.",
            "Attention mechanisms have become integral.",
            "2 Background",
            "Prior work relied on recurrent architectures.",
            "The encoder-decoder framework is standard.",
            "3 Model Architecture",
            "Our model is based entirely on attention mechanisms.",
            "We describe each component of the Transformer below.",
            "3.1 Encoder",
            "The encoder maps an input sequence to a sequence of representations.",
            "3.2 Decoder",
            "The decoder generates an output sequence one element at a time.",
            "4 Experiments",
            "We evaluate our model on machine translation benchmarks.",
            "Our model achieves state-of-the-art results.",
            "5 Conclusion",
            "We presented the Transformer architecture.",
            "References",
            "Vaswani et al. 2017. Attention Is All You Need.",
        ])
        lines = _clean_lines(text)
        sections = _build_sections(lines, paper_id="p1")
        headings = [s.heading for s in sections]
        assert len(sections) <= 15, f"Too many sections ({len(sections)}): {headings}"
        assert len(sections) >= 5, f"Too few sections ({len(sections)}): {headings}"
        # Known headings should be present
        assert "Abstract" in headings
        assert "1 Introduction" in headings
        assert "3 Model Architecture" in headings
        assert "4 Experiments" in headings


# ---------------------------------------------------------------------------
# Full structure_parse_result with boilerplate
# ---------------------------------------------------------------------------

class TestStructureWithBoilerplate:
    def test_copyright_block_does_not_pollute_title(self) -> None:
        raw_text = "\n".join([
            "Provided proper attribution is provided, Google hereby grants permission to",
            "reproduce the tables and figures in this paper solely for use in",
            "journalistic or scholarly works.",
            "",
            "Attention Is All You Need",
            "",
            "Ashish Vaswani, Noam Shazeer, Niki Parmar",
            "",
            "Abstract",
            "The dominant sequence transduction models are based on complex recurrent or",
            "convolutional neural networks. We propose a new architecture, the Transformer.",
            "",
            "1 Introduction",
            "Recurrent neural networks have been the dominant approach.",
        ])
        result = structure_parse_result(
            {"paper_id": "test-1", "raw_text": raw_text},
            source_url="https://arxiv.org/abs/1706.03762",
        )
        assert "Attention" in result.paper.title
        assert "permission" not in result.paper.title.lower()
        assert "scholarly" not in result.paper.title.lower()
