"""Lightweight metadata extraction and section structuring for parsed papers."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime

from backend.common.models import Author, Paper, Section, SectionType

_YEAR_PATTERN = re.compile(r"\b(19|20)\d{2}\b")
_NUMBERED_HEADING_PATTERN = re.compile(
    r"^(?P<number>(?:\d+(?:\.\d+)*|[IVXLC]+|[A-Z]))[\.\)]?\s+(?P<title>.+)$"
)
_APPENDIX_PATTERN = re.compile(r"^appendix(?:\s+[a-z0-9]+)?(?:[:.\-]\s+.+)?$", re.IGNORECASE)
_REFERENCE_PATTERN = re.compile(r"^(references|bibliography)$", re.IGNORECASE)
_ABSTRACT_PATTERN = re.compile(r"^abstract$", re.IGNORECASE)

# Patterns that indicate copyright / licence / venue boilerplate at the top of a PDF.
_BOILERPLATE_RE = re.compile(
    r"(?i)(?:"
    r"permission|copyright|©|license[ds]?\b|creative\s+commons|"
    r"arxiv:\s*\d|preprint|"
    r"hereby\s+grant|all\s+rights?\s+reserved|under\s+the\s+terms|"
    r"published\s+(?:in|by|at)\b|proceedings\s+of\b|"
    r"to\s+appear\s+in\b|accepted\s+(?:at|by)\b|submitted\s+to\b"
    r")"
)

_HEADING_TYPE_KEYWORDS: tuple[tuple[tuple[str, ...], SectionType], ...] = (
    (("abstract",), "abstract"),
    (("introduction", "intro"), "introduction"),
    (
        (
            "related work",
            "background",
            "prior work",
            "literature review",
        ),
        "related_work",
    ),
    (
        (
            "method",
            "methods",
            "methodology",
            "approach",
            "approaches",
            "model",
            "framework",
            "implementation",
        ),
        "methodology",
    ),
    (
        (
            "experiment",
            "experiments",
            "experimental setup",
            "evaluation",
            "evaluations",
            "results",
            "findings",
        ),
        "experiments",
    ),
    (("discussion",), "discussion"),
    (("conclusion", "conclusions", "future work"), "conclusion"),
    (("appendix", "supplementary"), "appendix"),
    (("references", "bibliography"), "references"),
)

_AUTHOR_SPLIT_PATTERN = re.compile(r"\s*(?:,|;|\band\b|·)\s*", re.IGNORECASE)
_AFFILIATION_HINTS = (
    "university",
    "institute",
    "school",
    "college",
    "laboratory",
    "lab",
    "department",
    "faculty",
    "research",
)


def _is_boilerplate_line(line: str) -> bool:
    """Return *True* when *line* looks like copyright / licence / venue boilerplate."""
    return _BOILERPLATE_RE.search(line) is not None


def _skip_leading_boilerplate(lines: Sequence[str]) -> list[str]:
    """Skip a contiguous boilerplate block at the very beginning of the paper.

    Many arXiv PDFs start with a copyright / permission notice before the title.
    We detect the first boilerplate line and then keep skipping until we reach a
    line that looks like genuine content (significant capitalisation, not a short
    trailing fragment).
    """
    first_bp = -1
    for i, line in enumerate(lines[:15]):
        if _is_boilerplate_line(line):
            first_bp = i
            break

    if first_bp == -1:
        return list(lines)

    skip_until = first_bp + 1
    for i in range(first_bp + 1, min(len(lines), first_bp + 10)):
        line = lines[i]
        if _is_boilerplate_line(line):
            skip_until = i + 1
            continue
        words = line.split()
        if not words:
            skip_until = i + 1
            continue
        # Short fragment ending with sentence punctuation (e.g. "scholarly works.")
        if len(words) <= 4 and line.rstrip()[-1:] in ".;:)":
            skip_until = i + 1
            continue
        # Long mostly-lowercase prose is likely a boilerplate continuation.
        cap_ratio = sum(1 for w in words if w[0].isupper()) / len(words)
        if len(words) > 8 and cap_ratio < 0.25:
            skip_until = i + 1
            continue
        break

    return list(lines[skip_until:])


@dataclass(frozen=True)
class StructuredPaper:
    """Structured output derived from the parser's raw text."""

    paper: Paper
    sections: list[Section]


def structure_parse_result(
    parse_result: Mapping[str, object],
    *,
    source_url: str | None = None,
    source_pdf_url: str | None = None,
) -> StructuredPaper:
    """Convert a parser result into Phase 1 paper metadata and sections."""

    paper_id = str(parse_result["paper_id"])
    raw_text = str(parse_result.get("raw_text", "") or "").strip()
    lines = _clean_lines(raw_text)

    title = _extract_title(lines)
    authors = _extract_authors(lines, title)
    abstract = _extract_abstract(raw_text, lines)
    year = _extract_year(lines)
    sections = _build_sections(lines, paper_id=paper_id)

    paper = Paper(
        paper_id=paper_id,
        title=title,
        authors=authors,
        abstract=abstract,
        year=year,
        url=source_url,
        pdf_url=source_pdf_url,
        status="parsed",
        updated_at=_utc_now_iso(),
        section_count=len(sections),
    )
    return StructuredPaper(paper=paper, sections=sections)


def _build_sections(lines: Sequence[str], *, paper_id: str) -> list[Section]:
    sections: list[Section] = []
    current_heading: str | None = None
    current_level = 1
    current_lines: list[str] = []

    for line in lines:
        if _looks_like_heading(line):
            if current_heading is not None:
                sections.append(
                    _section_from_parts(
                        paper_id=paper_id,
                        heading=current_heading,
                        level=current_level,
                        order_index=len(sections),
                        body_lines=current_lines,
                    )
                )
            current_heading = line
            current_level = _infer_heading_level(line)
            current_lines = []
            continue

        if current_heading is not None:
            current_lines.append(line)

    if current_heading is not None:
        sections.append(
            _section_from_parts(
                paper_id=paper_id,
                heading=current_heading,
                level=current_level,
                order_index=len(sections),
                body_lines=current_lines,
            )
        )

    if sections:
        return sections

    fallback_text = "\n".join(lines).strip()
    if not fallback_text:
        return []

    return [
        Section(
            paper_id=paper_id,
            heading="Body",
            section_type="other",
            level=1,
            order_index=0,
            text=fallback_text,
            char_count=len(fallback_text),
        )
    ]


def _section_from_parts(
    *,
    paper_id: str,
    heading: str,
    level: int,
    order_index: int,
    body_lines: Sequence[str],
) -> Section:
    text = "\n".join(body_lines).strip()
    if not text:
        text = heading.strip()

    return Section(
        paper_id=paper_id,
        heading=heading.strip(),
        section_type=_classify_section_type(heading),
        level=level,
        order_index=order_index,
        text=text,
        char_count=len(text),
    )


def _extract_title(lines: Sequence[str]) -> str:
    content_lines = _skip_leading_boilerplate(lines)
    meaningful = [line for line in content_lines[:12] if len(line) >= 8]
    if not meaningful:
        # Fallback to original lines when everything was filtered out.
        meaningful = [line for line in lines[:12] if len(line) >= 8]
    if not meaningful:
        return "Untitled Paper"

    title_lines: list[str] = []
    for line in meaningful:
        if _looks_like_heading(line):
            break
        if _looks_like_author_line(line) and title_lines:
            break
        if title_lines and (len(line) < 6 or line.endswith(".")):
            break
        title_lines.append(line)
        if len(" ".join(title_lines)) >= 160:
            break

    title = " ".join(title_lines).strip()
    return title or meaningful[0]


def _extract_authors(lines: Sequence[str], title: str) -> list[Author]:
    collected: list[str] = []
    passed_title = False

    for line in lines[:20]:
        if not passed_title:
            if line == title or title.startswith(line):
                passed_title = True
            continue

        normalized = line.strip()
        if _looks_like_heading(normalized):
            break
        if normalized.lower().startswith("keywords"):
            break
        if not normalized or "@" in normalized or any(hint in normalized.lower() for hint in _AFFILIATION_HINTS):
            continue
        if len(normalized.split()) > 8:
            continue
        # Strip common superscript markers before checking author pattern.
        cleaned = re.sub(r"[*∗†‡§¶\d]+$", "", normalized).strip()
        cleaned = re.sub(r"\s+[*∗†‡§¶\d]+(?=\s|$)", " ", cleaned).strip()
        if _looks_like_author_line(cleaned):
            collected.append(cleaned)

    if not collected:
        return []

    authors: list[Author] = []
    seen: set[str] = set()
    for block in collected:
        for candidate in _AUTHOR_SPLIT_PATTERN.split(block):
            name = re.sub(r"[*∗†‡§¶]+", "", " ".join(candidate.split())).strip()
            if not name or len(name.split()) > 5:
                continue
            if not re.fullmatch(r"[A-Za-z][A-Za-z.\-']*(?:\s+[A-Za-z][A-Za-z.\-']*){0,4}", name):
                continue
            key = name.casefold()
            if key in seen:
                continue
            seen.add(key)
            authors.append(Author(name=name))
    return authors


def _extract_abstract(raw_text: str, lines: Sequence[str]) -> str:
    abstract_match = re.search(
        r"(?ims)(?:^|\n)\s*abstract\s*\n(?P<body>.*?)(?:\n\s*(?:\d+(?:\.\d+)*[\.\)]?\s+)?"
        r"(?:introduction|related work|background|method|methods|methodology|approach|experiments|evaluation|results|discussion|conclusion|references)\b|\Z)",
        raw_text,
    )
    if abstract_match:
        return _collapse_whitespace(abstract_match.group("body"))

    try:
        abstract_index = next(
            index for index, line in enumerate(lines) if _ABSTRACT_PATTERN.fullmatch(line)
        )
    except StopIteration:
        return ""

    body: list[str] = []
    for line in lines[abstract_index + 1 :]:
        if _looks_like_heading(line):
            break
        body.append(line)
    return _collapse_whitespace("\n".join(body))


def _extract_year(lines: Sequence[str]) -> int | None:
    search_space = "\n".join(lines[:40])
    current_year = datetime.now(UTC).year + 1
    candidates = [
        int(match.group(0))
        for match in _YEAR_PATTERN.finditer(search_space)
        if 1900 <= int(match.group(0)) <= current_year
    ]
    if not candidates:
        return None
    return max(candidates)


def _clean_lines(raw_text: str) -> list[str]:
    cleaned: list[str] = []
    for raw_line in raw_text.splitlines():
        line = " ".join(raw_line.split()).strip()
        if not line:
            continue
        if re.fullmatch(r"\d{1,3}", line):
            continue
        cleaned.append(line)
    return cleaned


def _looks_like_heading(line: str) -> bool:
    stripped = line.strip()
    if len(stripped) < 3 or len(stripped) > 120:
        return False
    if stripped.endswith(".") and len(stripped.split()) > 2:
        return False
    if _ABSTRACT_PATTERN.fullmatch(stripped):
        return True
    if _REFERENCE_PATTERN.fullmatch(stripped):
        return True
    if _APPENDIX_PATTERN.fullmatch(stripped):
        return True
    numbered = _NUMBERED_HEADING_PATTERN.match(stripped)
    if numbered is not None:
        # A numbered prefix (e.g. "3.2") is strong evidence of a heading.
        # Only reject when the title part is sentence-length.
        title_part = numbered.group("title").strip()
        return len(title_part.split()) <= 8
    # Non-numbered headings must be short, start with an uppercase letter, and
    # contain a recognised section keyword.  This avoids classifying normal prose
    # lines that happen to mention words like "model" or "results".
    if len(stripped.split()) > 6 or len(stripped) > 60:
        return False
    if stripped[0].islower():
        return False
    return _is_heading_title(stripped)


def _is_heading_title(value: str) -> bool:
    lowered = value.casefold()
    return any(keyword in lowered for keywords, _section_type in _HEADING_TYPE_KEYWORDS for keyword in keywords)


def _infer_heading_level(heading: str) -> int:
    numbered = _NUMBERED_HEADING_PATTERN.match(heading.strip())
    if numbered is None:
        return 1
    number = numbered.group("number")
    if number.isalpha() and len(number) == 1:
        return 1
    if number.isupper() and len(number) > 1:
        return 1
    return number.count(".") + 1


def _classify_section_type(heading: str) -> SectionType:
    candidate = heading.strip()
    numbered = _NUMBERED_HEADING_PATTERN.match(candidate)
    if numbered is not None:
        candidate = numbered.group("title").strip()

    lowered = candidate.casefold()
    for keywords, section_type in _HEADING_TYPE_KEYWORDS:
        if any(keyword in lowered for keyword in keywords):
            return section_type
    return "other"


def _looks_like_author_line(value: str) -> bool:
    parts = [part for part in _AUTHOR_SPLIT_PATTERN.split(value) if part]
    if not parts:
        return False
    return all(1 <= len(part.split()) <= 4 for part in parts)


def _collapse_whitespace(value: str) -> str:
    return " ".join(value.split()).strip()


def _utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
