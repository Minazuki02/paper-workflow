"""Unit tests for the Phase 1 arXiv search provider."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.search.arxiv_provider import ArxivSearchProvider
from backend.search.base import SearchProviderError, SearchQuery

ARXIV_XML = b"""<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom" xmlns:arxiv="http://arxiv.org/schemas/atom">
  <title type="html">arXiv Query Results</title>
  <id>http://arxiv.org/api/pvS4t5X0</id>
  <updated>2026-04-10T00:00:00Z</updated>
  <totalResults>42</totalResults>
  <startIndex>0</startIndex>
  <itemsPerPage>2</itemsPerPage>
  <entry>
    <id>http://arxiv.org/abs/2401.12345v2</id>
    <updated>2024-01-20T12:00:00Z</updated>
    <published>2024-01-15T12:00:00Z</published>
    <title>
      Test Paper One
    </title>
    <summary>
      First abstract paragraph.
    </summary>
    <author><name>Alice Smith</name></author>
    <author><name>Bob Lee</name></author>
    <arxiv:doi>10.1000/example-doi</arxiv:doi>
    <link rel="alternate" type="text/html" href="http://arxiv.org/abs/2401.12345v2" />
    <link title="pdf" rel="related" type="application/pdf" href="http://arxiv.org/pdf/2401.12345v2" />
  </entry>
  <entry>
    <id>http://arxiv.org/abs/2301.99999v1</id>
    <updated>2023-02-02T12:00:00Z</updated>
    <published>2023-02-01T12:00:00Z</published>
    <title>Older Paper</title>
    <summary>Second abstract paragraph.</summary>
    <author><name>Carol Jones</name></author>
    <link rel="alternate" type="text/html" href="http://arxiv.org/abs/2301.99999v1" />
  </entry>
</feed>
"""


def test_arxiv_provider_maps_feed_entries_to_search_contract() -> None:
    provider = ArxivSearchProvider(fetcher=lambda _url, _timeout: ARXIV_XML)

    response = provider.search(SearchQuery(query="agent"))

    assert response.total_found == 42
    assert response.source_used == "arxiv"
    assert len(response.results) == 2

    first = response.results[0]
    assert first.title == "Test Paper One"
    assert first.authors == "Alice Smith, Bob Lee"
    assert first.year == 2024
    assert first.abstract == "First abstract paragraph."
    assert first.url == "http://arxiv.org/abs/2401.12345v2"
    assert first.pdf_url == "http://arxiv.org/pdf/2401.12345v2"
    assert first.doi == "10.1000/example-doi"
    assert first.citation_count is None
    assert first.source == "arxiv"
    assert first.already_ingested is False


def test_arxiv_provider_applies_year_filter_after_fetch() -> None:
    provider = ArxivSearchProvider(fetcher=lambda _url, _timeout: ARXIV_XML)

    response = provider.search(SearchQuery(query="agent", year_from=2024, year_to=2024))

    assert response.total_found == 1
    assert [result.title for result in response.results] == ["Test Paper One"]


def test_arxiv_provider_raises_structured_error_for_timeout() -> None:
    def timeout_fetcher(_url: str, _timeout: float) -> bytes:
        raise TimeoutError("boom")

    provider = ArxivSearchProvider(fetcher=timeout_fetcher)

    with pytest.raises(SearchProviderError) as exc_info:
        provider.search(SearchQuery(query="agent"))

    assert exc_info.value.error_code == "SEARCH_TIMEOUT"
