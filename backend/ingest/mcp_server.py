"""Minimal MCP server entrypoint for the Phase 1 ingest search slice."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from backend.ingest.tools import (
    handle_batch_ingest,
    handle_fetch_pdf,
    handle_get_ingest_status,
    handle_ingest_paper,
    handle_search_papers,
)


def create_server() -> FastMCP:
    """Create the Phase 1 ingest MCP server."""

    server = FastMCP("paper-ingest")

    @server.tool(
        name="search_papers",
        description="Search external academic paper sources and mark whether they already exist in the local library.",
        structured_output=True,
    )
    def search_papers(
        query: str,
        source: str = "all",
        year_from: int | None = None,
        year_to: int | None = None,
        max_results: int = 20,
        sort_by: str = "relevance",
    ) -> dict[str, object]:
        return handle_search_papers(
            query=query,
            source=source,
            year_from=year_from,
            year_to=year_to,
            max_results=max_results,
            sort_by=sort_by,
        )

    @server.tool(
        name="fetch_pdf",
        description="Download a single PDF to local storage without triggering ingest.",
        structured_output=True,
    )
    def fetch_pdf(url: str, filename: str | None = None) -> dict[str, object]:
        return handle_fetch_pdf(url=url, filename=filename)

    @server.tool(
        name="ingest_paper",
        description="Run the single-paper ingest pipeline and return a job identifier for progress polling.",
        structured_output=True,
    )
    def ingest_paper(
        url: str,
        doi: str | None = None,
        skip_if_exists: bool = True,
        parser: str = "pymupdf",
    ) -> dict[str, object]:
        return handle_ingest_paper(
            url=url,
            doi=doi,
            skip_if_exists=skip_if_exists,
            parser=parser,
        )

    @server.tool(
        name="get_ingest_status",
        description="Query the current ingest status for either a job_id or a paper_id.",
        structured_output=True,
    )
    def get_ingest_status(
        job_id: str | None = None,
        paper_id: str | None = None,
    ) -> dict[str, object]:
        return handle_get_ingest_status(job_id=job_id, paper_id=paper_id)

    @server.tool(
        name="batch_ingest",
        description="Run sequential batch ingest for multiple paper URLs and return a batch job identifier.",
        structured_output=True,
    )
    def batch_ingest(
        urls: list[str],
        options: dict[str, object] | None = None,
    ) -> dict[str, object]:
        return handle_batch_ingest(urls=urls, options=options)

    return server


def main() -> None:
    """Run the ingest MCP server over stdio."""

    create_server().run(transport="stdio")


if __name__ == "__main__":
    main()
