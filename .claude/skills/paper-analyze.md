---
name: paper-analyze
description: Deep structured analysis of a single ingested paper
aliases:
  - analyze-paper
  - paper-analysis
  - deep-read
whenToUse: >
  When the user wants a thorough analysis of one specific paper, including its
  contributions, methodology, findings, and limitations. Do not use it for
  multi-paper comparison or broad literature review work.
allowedTools:
  - mcp__paper_retrieval__retrieve_evidence
  - mcp__paper_ingest__get_ingest_status
  - TodoWrite
model: null
---

You are performing a structured analysis of a single paper in Phase 1.

1. Resolve the paper identity carefully.
   - If the user provides a `paper_id`, use it directly.
   - If the user provides an exact title, you may use `mcp__paper_retrieval__retrieve_evidence` with the title or distinctive keywords to infer a likely `paper_id` only when one paper clearly dominates the results.
   - If the identity is still ambiguous, stop and ask the user for the `paper_id` instead of guessing.

2. Confirm readiness before analysis.
   - Call `mcp__paper_ingest__get_ingest_status(paper_id=...)`.
   - Proceed only when the paper status is `ready`.
   - If the paper is missing or not ready, tell the user to ingest it first or wait for ingest to complete.

3. Infer the analysis focus from the request.
   - "How does this paper work?" or similar method questions: emphasize `methodology`.
   - "What did they find?" or result questions: emphasize `experiments`.
   - No special angle: produce a balanced full-paper analysis.

4. Gather evidence with targeted retrieval instead of calling an analysis backend.
   - Use `mcp__paper_retrieval__retrieve_evidence` scoped to the resolved `paper_id`.
   - Prefer multiple focused retrieval passes when needed, such as:
     - contribution or novelty query
     - methodology or approach query
     - experiments, results, or evaluation query
     - limitations, discussion, or failure cases query
   - When helpful, constrain `section_types` to `introduction`, `methodology`, `experiments`, `discussion`, or `conclusion`.

5. Produce the final analysis in this exact section order:
   - `Summary`
   - `Contributions`
   - `Methodology`
   - `Key Findings`
   - `Limitations`

6. Keep the analysis evidence-backed.
   - Base every section on retrieved chunks from the target paper.
   - After each bullet or short paragraph, attach the supporting quote details with paper title, year, section, page, and score.
   - If the current evidence is insufficient for one section, say that explicitly instead of filling the gap from unsupported prior knowledge.

7. Hard boundaries:
   - Do not call a nonexistent `analyze_paper` MCP tool.
   - Do not compare multiple papers here.
   - Do not write a survey or literature review here.
   - Do not read or write `data/` directly.
