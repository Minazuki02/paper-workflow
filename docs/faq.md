# FAQ

## Won't this mess up my Claude Code setup?

No. Install and uninstall are fully reversible:

- `install.sh` writes a manifest of every file it creates (`~/.claude/.paper-workflow-manifest.json`)
- `uninstall.sh` reads that manifest and removes exactly those files
- Your existing `~/.claude/settings.json` is merged, not replaced — and cleanly restored on uninstall
- `disable` / `enable` toggles in < 1 second without touching your data

If anything goes wrong, `bash scripts/uninstall.sh` is always a clean exit.

## Why not a standalone app?

Claude Code already solves the hard parts:

- **Natural language understanding** — you don't need to learn command syntax
- **Multi-step reasoning** — CC auto-decides whether to search, retrieve, or analyze
- **Tool orchestration** — search → download → ingest → retrieve → analyze, CC chains them automatically
- **Coding ability preserved** — finish analyzing papers, then immediately ask CC to write code based on what you learned, in the same session

We don't reinvent the wheel. We only add the missing paper capabilities.

## How is this different from asking ChatGPT to summarize a paper?

| | ChatGPT / asking an LLM directly | Paper Workflow |
|---|---|---|
| Data source | Training data (may be outdated or hallucinated) | PDFs you actually ingested |
| Verifiable | No way to check sources | Every evidence chunk includes paper title, page number, direct quote |
| Knowledge scope | Fixed at training cutoff | Grows as you ingest new papers |
| Retrieval | None | Vector search + full-text search + hybrid ranking |
| Analysis depth | Surface-level | Structured output: methodology, contributions, limitations, evidence chain |

**In one sentence: the LLM guesses, Paper Workflow looks it up.**

## Does this affect my normal coding workflow?

Not at all. Paper routing rules only activate when your request involves papers, literature, citations, or research evidence. Normal coding, debugging, and git operations work exactly as before — as if nothing was installed.

## Can I adapt this for my own domain?

Yes — this is one of the project's main design goals. The pattern (search → ingest → retrieve → analyze) with the lifecycle scripts (install → disable → enable → uninstall) applies to many domains:

- Patent search & analysis
- Legal case retrieval
- Internal knowledge base (wiki → searchable AI assistant)
- Financial report analysis
- Medical literature review

See the [Fork & Adapt Guide](fork-guide.md) for details.

## What models does it support?

Paper Workflow doesn't lock you into any specific model. Configure via `.env`:

| Setup | Embedding | LLM | Cost |
|-------|-----------|-----|------|
| Local | sentence-transformers | CC's built-in model | Free |
| API | Any OpenAI-compatible API | Any OpenAI-compatible API | Pay per use |
| Hybrid | Local embedding + remote LLM | Your choice | Low cost |

See [Configuration](configuration.md) for details.
