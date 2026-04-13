"""Semantic Scholar search provider implementation."""

from __future__ import annotations

import json
from collections.abc import Callable
from urllib import error as urllib_error
from urllib import parse, request as urllib_request

from backend.common.errors import (
    SEARCH_API_ERROR,
    SEARCH_INVALID_QUERY,
    SEARCH_RATE_LIMITED,
    SEARCH_TIMEOUT,
)
from backend.search.base import SearchProvider, SearchProviderError, SearchQuery, SearchResponse, SearchResult

S2_API_URL = "https://api.semanticscholar.org/graph/v1/paper/search"
S2_FIELDS = "title,authors,year,abstract,url,externalIds,citationCount,venue,openAccessPdf"


class SemanticScholarProvider(SearchProvider):
    """Search papers from the Semantic Scholar Academic Graph API."""

    source_name = "semantic_scholar"

    def __init__(
        self,
        *,
        base_url: str = S2_API_URL,
        api_key: str | None = None,
        timeout: float = 15.0,
        fetcher: Callable[[str, float, dict[str, str] | None], bytes] | None = None,
    ) -> None:
        self._base_url = base_url
        self._api_key = api_key
        self._timeout = timeout
        self._fetcher = fetcher or self._default_fetcher

    def search(self, request: SearchQuery) -> SearchResponse:
        if request.source not in {"semantic_scholar", "all"}:
            raise SearchProviderError(
                SEARCH_API_ERROR,
                f"Semantic Scholar provider does not support source={request.source!r}",
            )

        url = self._build_url(request)
        headers = self._build_headers()

        try:
            payload = self._fetcher(url, self._timeout, headers)
        except TimeoutError as exc:
            raise SearchProviderError(SEARCH_TIMEOUT, "Semantic Scholar search timed out") from exc
        except urllib_error.HTTPError as exc:
            if exc.code == 400:
                raise SearchProviderError(SEARCH_INVALID_QUERY, "Semantic Scholar rejected the query") from exc
            if exc.code == 429:
                raise SearchProviderError(SEARCH_RATE_LIMITED, "Semantic Scholar rate limited the request") from exc
            raise SearchProviderError(
                SEARCH_API_ERROR,
                f"Semantic Scholar search failed with HTTP {exc.code}",
            ) from exc
        except urllib_error.URLError as exc:
            reason = getattr(exc, "reason", None)
            if isinstance(reason, TimeoutError):
                raise SearchProviderError(SEARCH_TIMEOUT, "Semantic Scholar search timed out") from exc
            raise SearchProviderError(SEARCH_API_ERROR, "Semantic Scholar search request failed") from exc

        return self._parse_response(payload, request)

    def _build_url(self, search_query: SearchQuery) -> str:
        params: dict[str, str | int] = {
            "query": search_query.query,
            "limit": min(search_query.max_results, 100),
            "fields": S2_FIELDS,
        }

        if search_query.year_from is not None or search_query.year_to is not None:
            year_from = search_query.year_from or ""
            year_to = search_query.year_to or ""
            params["year"] = f"{year_from}-{year_to}"

        if search_query.sort_by == "citations":
            params["sort"] = "citationCount:desc"

        return f"{self._base_url}?{parse.urlencode(params)}"

    def _build_headers(self) -> dict[str, str] | None:
        if not self._api_key:
            return None
        return {"x-api-key": self._api_key}

    def _parse_response(self, payload: bytes, search_query: SearchQuery) -> SearchResponse:
        try:
            data = json.loads(payload)
        except json.JSONDecodeError as exc:
            raise SearchProviderError(SEARCH_API_ERROR, "Semantic Scholar returned malformed JSON") from exc

        if "data" not in data:
            if "message" in data:
                raise SearchProviderError(SEARCH_API_ERROR, f"Semantic Scholar: {data['message']}")
            raise SearchProviderError(SEARCH_API_ERROR, "Semantic Scholar returned unexpected response format")

        total_found = data.get("total", len(data["data"]))
        results = [self._parse_paper(paper) for paper in data["data"] if paper]

        return SearchResponse(
            results=results[:search_query.max_results],
            total_found=total_found,
            source_used=self.source_name,
        )

    def _parse_paper(self, paper: dict) -> SearchResult:
        authors_list = paper.get("authors") or []
        authors_str = ", ".join(a.get("name", "") for a in authors_list if a.get("name"))

        external_ids = paper.get("externalIds") or {}
        doi = external_ids.get("DOI")
        arxiv_id = external_ids.get("ArXiv")

        pdf_url = None
        open_access = paper.get("openAccessPdf")
        if isinstance(open_access, dict):
            pdf_url = open_access.get("url")
        if not pdf_url and arxiv_id:
            pdf_url = f"https://arxiv.org/pdf/{arxiv_id}"

        url = paper.get("url") or ""
        if not url and paper.get("paperId"):
            url = f"https://www.semanticscholar.org/paper/{paper['paperId']}"

        return SearchResult(
            title=paper.get("title") or "Untitled",
            authors=authors_str,
            year=paper.get("year"),
            abstract=paper.get("abstract") or "",
            url=url,
            pdf_url=pdf_url,
            doi=doi,
            citation_count=paper.get("citationCount"),
            source=self.source_name,
            already_ingested=False,
        )

    def _default_fetcher(self, url: str, timeout: float, headers: dict[str, str] | None) -> bytes:
        req = urllib_request.Request(url)
        if headers:
            for key, value in headers.items():
                req.add_header(key, value)
        with urllib_request.urlopen(req, timeout=timeout) as response:
            return response.read()
