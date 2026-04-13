---
name: paper-ingest
description: Download, parse, and index papers into the local library
aliases:
  - ingest-paper
  - ingest
  - download-paper
whenToUse: >
  When the user provides paper URLs, DOIs, or arXiv IDs and wants them added to
  the local library. Also use it as the follow-up after a paper search selection.
allowedTools:
  - mcp__paper_ingest__ingest_paper
  - mcp__paper_ingest__batch_ingest
  - mcp__paper_ingest__get_ingest_status
  - mcp__paper_ingest__fetch_pdf
  - TodoWrite
  - AskUserQuestion
model: null
---

You are handling a paper ingest request.

1. Parse the user's input to extract URLs, DOIs, or arXiv IDs.
   - If the input is an arXiv ID like `2401.12345`, convert it to `https://arxiv.org/abs/2401.12345`.
   - If the input is a DOI, keep the DOI available while resolving the ingest call.

2. Route by batch size:
   - For 1-3 papers, call `mcp__paper_ingest__ingest_paper` sequentially and poll `mcp__paper_ingest__get_ingest_status` for each job until it settles.
   - For 4 or more papers, delegate the batch work to the `ingest-operator` subagent instead of calling `ingest_paper` in a loop.

3. Track progress with `TodoWrite`.
   - Use one in-progress todo per current paper or batch.
   - Mark completed, failed, or skipped states as status updates arrive.

4. Keep the scope limited to ingest orchestration.
   - Do not search for new papers here.
   - Do not analyze papers here.
   - Do not read or write the `data/` directory directly.

5. Final report format:
   - success count
   - failed count with error details
   - skipped count with existing paper references when available
   - relevant `job_id` values for follow-up status checks
