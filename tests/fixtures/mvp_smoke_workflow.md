# MVP Smoke Workflow

Scenario: "搜索 transformer 论文，下载前 3 篇，入库，查询 attention mechanism，分析第一篇"

Pre-check:
- Run `python scripts/health_check.py` and confirm both `paper-ingest` and `paper-retrieval` report `ok`.

Smoke steps:
1. `/paper-search "transformer attention"`
   Expected: markdown table with at least several candidate papers and no fabricated metadata.
2. `/paper-ingest` for the selected top 3 papers
   Expected: queued or skipped status per paper, plus `job_id` for status polling.
3. `/paper-status`
   Expected: the selected papers eventually reach `ready`, or the failure contains `error_code` and `stage`.
4. `/paper-evidence "what are the main types of attention mechanisms"`
   Expected: evidence output includes direct quotes, title, authors, year, section/page, and score.
5. `/paper-analyze [paper_id of first ready paper]`
   Expected: output remains in `Summary -> Contributions -> Methodology -> Key Findings -> Limitations` order and cites retrieved evidence instead of a nonexistent analysis MCP tool.

Phase 1 boundary reminders:
- Do not call a separate Analysis MCP server.
- Do not read or write `data/` directly from the orchestrator.
- Use `retrieve_evidence` scoped to a single `paper_id` when supporting `/paper-analyze`.
