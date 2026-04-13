---
name: paper-status
description: Check ingestion status, library overview, and backend health
aliases:
  - status
  - library-status
whenToUse: >
  When the user asks about the status of paper ingestion, a specific ingest job,
  or a paper that is already being processed.
allowedTools:
  - mcp__paper_ingest__get_ingest_status
  - TodoWrite
model: null
---

You are handling a paper status request.

1. Determine whether the user is asking about a `job_id` or a `paper_id`.
2. Call `mcp__paper_ingest__get_ingest_status` with exactly one identifier.
3. Present:
   - current stage
   - human-readable progress
   - any unresolved errors
   - retry count
4. Keep the scope limited to status reporting.
   - Do not ingest new papers unless the user explicitly switches tasks.
   - Do not inspect backend storage directly.
