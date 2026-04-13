"""Minimal MCP server entrypoint for the Phase 1 retrieval slice."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from backend.common.models import SectionType
from backend.retrieval.tools import handle_retrieve_evidence


def create_server() -> FastMCP:
    """Create the Phase 1 retrieval MCP server."""

    server = FastMCP("paper-retrieval")

    @server.tool(
        name="retrieve_evidence",
        description="Retrieve relevant evidence chunks from ready papers using vector, text, or hybrid search.",
        structured_output=True,
    )
    def retrieve_evidence(
        query: str,
        top_k: int = 10,
        paper_ids: list[str] | None = None,
        section_types: list[SectionType] | None = None,
        year_from: int | None = None,
        year_to: int | None = None,
        search_mode: str = "hybrid",
        min_score: float = 0.3,
    ) -> dict[str, object]:
        return handle_retrieve_evidence(
            query=query,
            top_k=top_k,
            paper_ids=paper_ids,
            section_types=section_types,
            year_from=year_from,
            year_to=year_to,
            search_mode=search_mode,
            min_score=min_score,
        )

    return server


def main() -> None:
    """Run the retrieval MCP server over stdio."""

    create_server().run(transport="stdio")


if __name__ == "__main__":
    main()
