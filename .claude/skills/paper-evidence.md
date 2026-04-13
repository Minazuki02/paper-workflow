---
name: paper-evidence
description: Retrieve evidence from ingested papers to answer research questions
aliases:
  - query-papers
  - find-evidence
  - ask-papers
whenToUse: >
  When the user asks a research question that should be answered using evidence
  from ingested papers. Do not use it for general web knowledge or for finding
  new papers outside the current library.
allowedTools:
  - mcp__paper_retrieval__retrieve_evidence
  - mcp__paper_ingest__get_ingest_status
  - TodoWrite
model: null
---

You are retrieving evidence from the ingested paper library.

1. Normalize the user's research question into a retrieval query.
   - Remove conversational filler.
   - Keep domain-specific terms, model names, dataset names, and technical phrases.
   - If the question is broad, split it into at most 2-3 focused retrieval queries.

2. Call `mcp__paper_retrieval__retrieve_evidence` with:
   - the optimized query
   - `top_k=10` by default, or up to `20` when the user clearly wants broad coverage
   - `paper_ids` only when the user explicitly limits the scope
   - `section_types` inferred from the question when helpful

3. Present evidence grouped by paper.
   - For each hit, include the direct quote, `paper_id`, paper title, authors, year, section type, page number, and score.
   - Keep the response evidence-focused. Do not turn it into a full paper analysis or a literature review.

4. If there are no strong hits or all scores are below `0.3`, say:
   `I found no strong evidence for this in the ingested papers.`
   Then briefly suggest the next in-scope step, such as refining the question or ingesting more papers.

5. Hard boundaries:
   - Do not search external sources here.
   - Do not ingest papers here.
   - Do not read or write `data/` directly.
