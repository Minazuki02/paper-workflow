"""arXiv search provider implementation for the Phase 1 paper search flow."""

from __future__ import annotations

from collections.abc import Callable
from urllib import error as urllib_error
from urllib import parse, request as urllib_request
from xml.etree import ElementTree

from backend.common.errors import (
    SEARCH_API_ERROR,
    SEARCH_INVALID_QUERY,
    SEARCH_RATE_LIMITED,
    SEARCH_TIMEOUT,
)
from backend.search.base import SearchProvider, SearchProviderError, SearchQuery, SearchResponse, SearchResult

ARXIV_API_URL = "https://export.arxiv.org/api/query"
ATOM_NAMESPACE = {"atom": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}


class ArxivSearchProvider(SearchProvider):
    """Search papers from arXiv and normalize them to the shared contract."""

    source_name = "arxiv"

    def __init__(
        self,
        *,
        base_url: str = ARXIV_API_URL,
        timeout: float = 15.0,
        fetcher: Callable[[str, float], bytes] | None = None,
    ) -> None:
        self._base_url = base_url
        self._timeout = timeout
        self._fetcher = fetcher or self._default_fetcher

    def search(self, request: SearchQuery) -> SearchResponse:
        if request.source not in {"arxiv", "all"}:
            raise SearchProviderError(
                SEARCH_API_ERROR,
                f"arXiv provider does not support source={request.source!r}",
            )

        try:
            payload = self._fetcher(self._build_url(request), self._timeout)
        except TimeoutError as exc:
            raise SearchProviderError(SEARCH_TIMEOUT, "arXiv search timed out") from exc
        except urllib_error.HTTPError as exc:
            if exc.code == 400:
                raise SearchProviderError(SEARCH_INVALID_QUERY, "arXiv rejected the query") from exc
            if exc.code == 429:
                raise SearchProviderError(SEARCH_RATE_LIMITED, "arXiv rate limited the request") from exc
            raise SearchProviderError(
                SEARCH_API_ERROR,
                f"arXiv search failed with HTTP {exc.code}",
            ) from exc
        except urllib_error.URLError as exc:
            reason = getattr(exc, "reason", None)
            if isinstance(reason, TimeoutError):
                raise SearchProviderError(SEARCH_TIMEOUT, "arXiv search timed out") from exc
            raise SearchProviderError(SEARCH_API_ERROR, "arXiv search request failed") from exc

        return self._parse_response(payload, request)

    def _build_url(self, search_query: SearchQuery) -> str:
        # arXiv does not support citation sorting, so keep the request deterministic
        # by falling back to relevance for that case.
        sort_by = {
            "relevance": "relevance",
            "date": "submittedDate",
            "citations": "relevance",
        }[search_query.sort_by]

        max_results = search_query.max_results
        if search_query.year_from is not None or search_query.year_to is not None:
            max_results = min(max_results * 4, 100)

        params = {
            "search_query": f"all:{search_query.query}",
            "start": 0,
            "max_results": max_results,
            "sortBy": sort_by,
            "sortOrder": "descending",
        }
        return f"{self._base_url}?{parse.urlencode(params)}"

    def _parse_response(self, payload: bytes, search_query: SearchQuery) -> SearchResponse:
        try:
            root = ElementTree.fromstring(payload)
        except ElementTree.ParseError as exc:
            raise SearchProviderError(SEARCH_API_ERROR, "arXiv returned malformed XML") from exc

        total_found = int(root.findtext("atom:totalResults", default="0", namespaces=ATOM_NAMESPACE))
        parsed_results = [
            self._parse_entry(entry)
            for entry in root.findall("atom:entry", ATOM_NAMESPACE)
        ]
        filtered_results = self._filter_by_year(parsed_results, search_query)

        return SearchResponse(
            results=filtered_results[: search_query.max_results],
            total_found=len(filtered_results)
            if search_query.year_from is not None or search_query.year_to is not None
            else total_found,
            source_used=self.source_name,
        )

    def _parse_entry(self, entry: ElementTree.Element) -> SearchResult:
        authors = [
            author.findtext("atom:name", default="", namespaces=ATOM_NAMESPACE).strip()
            for author in entry.findall("atom:author", ATOM_NAMESPACE)
        ]
        cleaned_authors = ", ".join(author for author in authors if author)

        title = self._normalize_text(entry.findtext("atom:title", default="", namespaces=ATOM_NAMESPACE))
        abstract = self._normalize_text(entry.findtext("atom:summary", default="", namespaces=ATOM_NAMESPACE))
        published = entry.findtext("atom:published", default="", namespaces=ATOM_NAMESPACE)
        year = int(published[:4]) if len(published) >= 4 and published[:4].isdigit() else None

        pdf_url = None
        for link in entry.findall("atom:link", ATOM_NAMESPACE):
            if link.attrib.get("title") == "pdf" or link.attrib.get("type") == "application/pdf":
                pdf_url = link.attrib.get("href")
                break

        doi = entry.findtext("arxiv:doi", default=None, namespaces=ATOM_NAMESPACE)
        landing_url = self._normalize_text(entry.findtext("atom:id", default="", namespaces=ATOM_NAMESPACE))

        return SearchResult(
            title=title,
            authors=cleaned_authors,
            year=year,
            abstract=abstract,
            url=landing_url,
            pdf_url=pdf_url,
            doi=doi.strip() if isinstance(doi, str) else None,
            citation_count=None,
            source=self.source_name,
            already_ingested=False,
        )

    def _filter_by_year(
        self,
        results: list[SearchResult],
        search_query: SearchQuery,
    ) -> list[SearchResult]:
        year_from = search_query.year_from
        year_to = search_query.year_to

        if year_from is None and year_to is None:
            return results

        filtered: list[SearchResult] = []
        for result in results:
            if result.year is None:
                continue
            if year_from is not None and result.year < year_from:
                continue
            if year_to is not None and result.year > year_to:
                continue
            filtered.append(result)
        return filtered

    def _default_fetcher(self, url: str, timeout: float) -> bytes:
        with urllib_request.urlopen(url, timeout=timeout) as response:
            return response.read()

    @staticmethod
    def _normalize_text(value: str) -> str:
        return " ".join(value.split())
