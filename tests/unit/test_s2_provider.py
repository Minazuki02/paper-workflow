"""Unit tests for the Semantic Scholar search provider."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.search.base import SearchProviderError, SearchQuery
from backend.search.s2_provider import SemanticScholarProvider

S2_JSON = json.dumps({
    "total": 156,
    "offset": 0,
    "data": [
        {
            "paperId": "abc123",
            "title": "Attention Is All You Need",
            "authors": [
                {"authorId": "1", "name": "Ashish Vaswani"},
                {"authorId": "2", "name": "Noam Shazeer"},
            ],
            "year": 2017,
            "abstract": "The dominant sequence transduction models are based on complex recurrent or convolutional neural networks.",
            "url": "https://www.semanticscholar.org/paper/abc123",
            "venue": "NeurIPS",
            "citationCount": 120000,
            "externalIds": {
                "DOI": "10.5555/3295222.3295349",
                "ArXiv": "1706.03762",
            },
            "openAccessPdf": {
                "url": "https://arxiv.org/pdf/1706.03762",
                "status": "GREEN",
            },
        },
        {
            "paperId": "def456",
            "title": "BERT: Pre-training of Deep Bidirectional Transformers",
            "authors": [
                {"authorId": "3", "name": "Jacob Devlin"},
            ],
            "year": 2019,
            "abstract": "We introduce BERT.",
            "url": "https://www.semanticscholar.org/paper/def456",
            "venue": "NAACL",
            "citationCount": 80000,
            "externalIds": {"DOI": "10.18653/v1/N19-1423"},
            "openAccessPdf": None,
        },
        {
            "paperId": "ghi789",
            "title": "GPT-4 Technical Report",
            "authors": [],
            "year": 2023,
            "abstract": None,
            "url": "",
            "venue": "",
            "citationCount": 5000,
            "externalIds": {},
            "openAccessPdf": None,
        },
    ],
}).encode()


def _mock_fetcher(response_bytes: bytes):
    def fetcher(_url: str, _timeout: float, _headers: dict | None) -> bytes:
        return response_bytes
    return fetcher


class TestSemanticScholarProvider:
    def test_maps_api_response_to_search_contract(self) -> None:
        provider = SemanticScholarProvider(fetcher=_mock_fetcher(S2_JSON))
        response = provider.search(SearchQuery(query="transformer"))

        assert response.total_found == 156
        assert response.source_used == "semantic_scholar"
        assert len(response.results) == 3

    def test_first_result_fields(self) -> None:
        provider = SemanticScholarProvider(fetcher=_mock_fetcher(S2_JSON))
        result = provider.search(SearchQuery(query="transformer")).results[0]

        assert result.title == "Attention Is All You Need"
        assert "Ashish Vaswani" in result.authors
        assert "Noam Shazeer" in result.authors
        assert result.year == 2017
        assert result.doi == "10.5555/3295222.3295349"
        assert result.citation_count == 120000
        assert result.pdf_url == "https://arxiv.org/pdf/1706.03762"
        assert result.source == "semantic_scholar"
        assert result.already_ingested is False

    def test_result_without_open_access_pdf_uses_arxiv_fallback(self) -> None:
        """When openAccessPdf is None but ArXiv ID exists, construct PDF URL."""
        data = json.dumps({
            "total": 1,
            "data": [{
                "paperId": "x",
                "title": "Some Paper",
                "authors": [{"name": "Alice"}],
                "year": 2024,
                "abstract": "Abstract.",
                "url": "https://www.semanticscholar.org/paper/x",
                "citationCount": 10,
                "externalIds": {"ArXiv": "2401.00001"},
                "openAccessPdf": None,
            }],
        }).encode()
        provider = SemanticScholarProvider(fetcher=_mock_fetcher(data))
        result = provider.search(SearchQuery(query="test")).results[0]
        assert result.pdf_url == "https://arxiv.org/pdf/2401.00001"

    def test_result_without_any_pdf_info(self) -> None:
        data = json.dumps({
            "total": 1,
            "data": [{
                "paperId": "x",
                "title": "Closed Paper",
                "authors": [],
                "year": 2024,
                "abstract": "",
                "url": "https://www.semanticscholar.org/paper/x",
                "citationCount": 0,
                "externalIds": {},
                "openAccessPdf": None,
            }],
        }).encode()
        provider = SemanticScholarProvider(fetcher=_mock_fetcher(data))
        result = provider.search(SearchQuery(query="test")).results[0]
        assert result.pdf_url is None

    def test_empty_url_gets_constructed_from_paper_id(self) -> None:
        provider = SemanticScholarProvider(fetcher=_mock_fetcher(S2_JSON))
        result = provider.search(SearchQuery(query="test")).results[2]
        assert "ghi789" in result.url

    def test_year_filter_passed_in_url(self) -> None:
        """Verify year range is sent as query parameter."""
        captured_urls: list[str] = []

        def capturing_fetcher(url: str, _timeout: float, _headers: dict | None) -> bytes:
            captured_urls.append(url)
            return S2_JSON

        provider = SemanticScholarProvider(fetcher=capturing_fetcher)
        provider.search(SearchQuery(query="test", year_from=2020, year_to=2024))
        assert "year=2020-2024" in captured_urls[0]

    def test_citation_sort_passed_in_url(self) -> None:
        captured_urls: list[str] = []

        def capturing_fetcher(url: str, _timeout: float, _headers: dict | None) -> bytes:
            captured_urls.append(url)
            return S2_JSON

        provider = SemanticScholarProvider(fetcher=capturing_fetcher)
        provider.search(SearchQuery(query="test", sort_by="citations"))
        assert "sort=citationCount" in captured_urls[0]

    def test_api_key_sent_as_header(self) -> None:
        captured_headers: list[dict | None] = []

        def capturing_fetcher(_url: str, _timeout: float, headers: dict | None) -> bytes:
            captured_headers.append(headers)
            return S2_JSON

        provider = SemanticScholarProvider(api_key="test-key-123", fetcher=capturing_fetcher)
        provider.search(SearchQuery(query="test"))
        assert captured_headers[0] is not None
        assert captured_headers[0]["x-api-key"] == "test-key-123"

    def test_no_api_key_sends_no_header(self) -> None:
        captured_headers: list[dict | None] = []

        def capturing_fetcher(_url: str, _timeout: float, headers: dict | None) -> bytes:
            captured_headers.append(headers)
            return S2_JSON

        provider = SemanticScholarProvider(fetcher=capturing_fetcher)
        provider.search(SearchQuery(query="test"))
        assert captured_headers[0] is None

    def test_malformed_json_raises(self) -> None:
        provider = SemanticScholarProvider(fetcher=_mock_fetcher(b"not json"))
        with pytest.raises(SearchProviderError) as exc_info:
            provider.search(SearchQuery(query="test"))
        assert exc_info.value.error_code == "SEARCH_API_ERROR"

    def test_api_error_message_surfaced(self) -> None:
        data = json.dumps({"message": "Bad request: query too long"}).encode()
        provider = SemanticScholarProvider(fetcher=_mock_fetcher(data))
        with pytest.raises(SearchProviderError) as exc_info:
            provider.search(SearchQuery(query="test"))
        assert "Bad request" in exc_info.value.message

    def test_max_results_respected(self) -> None:
        provider = SemanticScholarProvider(fetcher=_mock_fetcher(S2_JSON))
        response = provider.search(SearchQuery(query="test", max_results=2))
        assert len(response.results) <= 2

    def test_wrong_source_raises(self) -> None:
        provider = SemanticScholarProvider(fetcher=_mock_fetcher(S2_JSON))
        with pytest.raises(SearchProviderError):
            provider.search(SearchQuery(query="test", source="arxiv"))
