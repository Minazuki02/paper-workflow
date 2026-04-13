# Paper Routing

When the user's request involves academic papers, literature review, citations, or research evidence, switch into paper workflow mode.

1. Detect paper intent early.
   - If the user asks about papers, literature, citations, prior work, or research findings, route to paper tools instead of answering from model memory alone.
   - If paper tools cannot support the request, say that explicitly.

2. Route by intent.
   - Search or discovery requests: use `mcp__paper_ingest__search_papers`.
   - Ingest or download requests: use `mcp__paper_ingest__ingest_paper`, `mcp__paper_ingest__batch_ingest`, or `mcp__paper_ingest__fetch_pdf` as appropriate.
   - Evidence requests against the local library: use `mcp__paper_retrieval__retrieve_evidence`.
   - Single-paper analysis in Phase 1: confirm the paper is `ready` with `mcp__paper_ingest__get_ingest_status`, gather supporting chunks with `mcp__paper_retrieval__retrieve_evidence`, and synthesize the structured analysis in the orchestrator. Do not call a nonexistent analysis MCP tool.
   - Status checks: use `mcp__paper_ingest__get_ingest_status`.

3. Respect tool boundaries.
   - Do not read or write `data/` directly.
   - Do not turn the orchestrator into a PDF parser, embedding worker, retriever implementation, or storage operator.
   - For batch ingest requests covering more than 3 papers, prefer `batch_ingest` over looping `ingest_paper`.

4. Preserve coding behavior outside paper requests.
   - If the user mixes coding work and paper work, finish or clearly stage the paper operation first, then continue with coding.
   - Do not let paper workflow rules degrade ordinary coding assistance.

5. Never fabricate academic metadata.
   - Do not invent paper titles, authors, venues, years, DOIs, or citations.
   - If the tool output is missing or ambiguous, say so instead of guessing.
