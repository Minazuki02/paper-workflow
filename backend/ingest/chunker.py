"""Fixed-parameter chunking for Phase 1 retrieval readiness."""

from __future__ import annotations

import re
from collections.abc import Sequence

from backend.common.models import Chunk, Section

CHUNK_TOKEN_SIZE = 512
CHUNK_TOKEN_OVERLAP = 128
DEFAULT_EMBEDDING_MODEL = "all-MiniLM-L6-v2"

_TOKEN_PATTERN = re.compile(r"\S+")


def chunk_sections(
    sections: Sequence[Section],
    *,
    embedding_model: str = DEFAULT_EMBEDDING_MODEL,
) -> list[Chunk]:
    """Split section text into stable retrieval chunks with fixed overlap."""

    chunks: list[Chunk] = []

    for section in sections:
        token_spans = list(_iter_token_spans(section.text))
        if not token_spans:
            continue

        start_index = 0
        while start_index < len(token_spans):
            end_index = min(start_index + CHUNK_TOKEN_SIZE, len(token_spans))
            chunk_text = _slice_tokens(section.text, token_spans, start_index, end_index)
            if not chunk_text:
                break

            chunks.append(
                Chunk(
                    paper_id=section.paper_id,
                    section_id=section.section_id,
                    text=chunk_text,
                    char_count=len(chunk_text),
                    token_count=end_index - start_index,
                    order_index=len(chunks),
                    page_start=None,
                    page_end=None,
                    embedding_model=embedding_model,
                    section_type=section.section_type,
                    heading=section.heading,
                )
            )

            if end_index >= len(token_spans):
                break

            start_index = end_index - CHUNK_TOKEN_OVERLAP

    return chunks


def _iter_token_spans(text: str):
    for match in _TOKEN_PATTERN.finditer(text):
        yield match.start(), match.end()


def _slice_tokens(
    text: str,
    token_spans: Sequence[tuple[int, int]],
    start_index: int,
    end_index: int,
) -> str:
    start_char = token_spans[start_index][0]
    end_char = token_spans[end_index - 1][1]
    return text[start_char:end_char].strip()
