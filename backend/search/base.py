"""Shared models and interfaces for external paper search providers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

SearchSource = Literal["arxiv", "semantic_scholar", "all"]
SearchSortBy = Literal["relevance", "date", "citations"]


class SearchModel(BaseModel):
    """Base model for search-slice contracts."""

    model_config = ConfigDict(extra="forbid")


class SearchQuery(SearchModel):
    """Validated search input used by provider implementations."""

    query: str
    source: SearchSource = "all"
    year_from: int | None = None
    year_to: int | None = None
    max_results: int = Field(default=20, ge=1, le=100)
    sort_by: SearchSortBy = "relevance"

    @field_validator("query")
    @classmethod
    def validate_query(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("query must not be empty")
        return normalized

    @field_validator("year_to")
    @classmethod
    def validate_year_range(cls, value: int | None, info) -> int | None:
        year_from = info.data.get("year_from")
        if value is not None and year_from is not None and value < year_from:
            raise ValueError("year_to must be greater than or equal to year_from")
        return value


class SearchResult(SearchModel):
    """User-visible paper search result contract from 02_schema_and_tool_contracts."""

    title: str
    authors: str
    year: int | None = None
    abstract: str
    url: str
    pdf_url: str | None = None
    doi: str | None = None
    citation_count: int | None = None
    source: str
    already_ingested: bool = False


class SearchResponse(SearchModel):
    """Canonical output payload for the search_papers MCP tool."""

    results: list[SearchResult]
    total_found: int
    source_used: str


class SearchProviderError(Exception):
    """Raised when a search provider fails with a tool-level error semantic."""

    def __init__(self, error_code: str, message: str) -> None:
        super().__init__(message)
        self.error_code = error_code
        self.message = message


class SearchProvider(ABC):
    """Abstract interface implemented by concrete external search providers."""

    source_name: str

    @abstractmethod
    def search(self, request: SearchQuery) -> SearchResponse:
        """Run a search request and return provider-normalized results."""

