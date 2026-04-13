# Paper Workflow

> Turn Claude Code into a research assistant. Install in one command, remove in one command. Zero residue.

<p align="center"><a href="README.zh-CN.md">中文版 README</a></p>

**把 Claude Code 变成论文研究助手——零侵入安装，一键拆卸。**

[![Release](https://img.shields.io/github/v/release/Minazuki02/paper-workflow?include_prereleases&label=release&color=blue)](https://github.com/Minazuki02/paper-workflow/releases)
[![Status: Alpha](https://img.shields.io/badge/status-alpha-orange)]()
[![Python](https://img.shields.io/badge/python-≥3.11-3776AB?logo=python&logoColor=white)](https://python.org)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-89_cases-brightgreen)]()
[![MCP](https://img.shields.io/badge/protocol-MCP-8A2BE2)](https://modelcontextprotocol.io)

<img width="720" alt="Paper Workflow" src="https://github.com/user-attachments/assets/b64ccfb1-ea0a-4136-90b5-ab92e4533910" />

---

## What it does

```
you: /paper-search "LLM agent reasoning 2024"
 CC: Found 20 papers across arXiv + Semantic Scholar…

you: /paper-ingest 1,3,5
 CC: 3 papers downloaded, parsed, embedded, and indexed ✓

you: What attention variants exist in the literature?
 CC: Based on 8 evidence chunks from your library:
     > "Multi-head attention allows the model to jointly attend…"
     > — Attention Is All You Need (Vaswani et al., 2017), §3.2, p.4, score: 0.87
```

Every claim is backed by a direct quote from the actual PDF — not the model's training data.

<!-- TODO: Add terminal screenshots when available
<details>
<summary><strong>See it in action (screenshots)</strong></summary>

**Search & ingest papers:**
<img width="680" alt="paper-search demo" src="docs/screenshots/search-ingest.png" />

**Evidence retrieval with source tracking:**
<img width="680" alt="evidence retrieval demo" src="docs/screenshots/evidence-retrieval.png" />

</details>
-->

---

## Why this project

- **Evidence-first, not guessing.** Ask a research question → get exact quotes with paper title, page number, and relevance score. Not LLM hallucinations.
- **Zero CC modification.** Installs through Claude Code's official extension system (Skills + MCP + Rules). Your coding workflow is untouched.
- **Fully removable.** `install.sh` writes a manifest. `uninstall.sh` reads it and removes exactly those files. Disable/enable in < 1 second.

---

## Quick Start

### Already have Claude Code?

```bash
git clone https://github.com/Minazuki02/paper-workflow.git
cd paper-workflow
bash scripts/install.sh
```

Then start `claude` **from any directory** — paper tools are globally available:

```bash
claude
# Try: /paper-search "transformer attention"
```

Toggle paper mode on/off without touching your data:

```bash
bash scripts/paper-workflow.sh disable   # pure coding mode
bash scripts/paper-workflow.sh enable    # paper tools back
```

Full removal: `bash scripts/uninstall.sh`

> **Requirements:** Python ≥ 3.11 · [Claude Code](https://docs.anthropic.com/en/docs/claude-code) installed

### Just exploring?

No Claude Code needed to browse the codebase or run backend tests:

```bash
git clone https://github.com/Minazuki02/paper-workflow.git
cd paper-workflow
pip install -e backend[dev]
pytest tests/
```

See [Architecture →](docs/01_architecture_and_boundaries.md) for how it works.

---

## How it works

```
┌─────────────────────────────┐
│ Claude Code  (unmodified)   │
│  Skills · Agents · Rules    │
│         ↕ MCP (stdio)       │
├─────────────────────────────┤
│ Python Backend (this repo)  │
│  Ingest → Retrieve → Analyze│
│  SQLite + FAISS + PDF store │
└─────────────────────────────┘
```

CC stays the orchestrator. The backend does all heavy lifting (PDF parsing, embedding, retrieval) through [MCP](https://modelcontextprotocol.io).

**Design principles:**
- CC doesn't touch data. Backend doesn't touch users. MCP bridges the two.
- Everything injected into `~/.claude/` is tracked by a manifest — nothing is left behind on uninstall.
- CC source code is never modified. All capabilities come through the official extension system.

[Full architecture →](docs/01_architecture_and_boundaries.md)

---

## Status — v0.1.0-alpha

> This is an **early alpha**. The core pipeline works end-to-end, but rough edges exist.

| Feature | Status |
|---------|--------|
| Multi-source search (arXiv + Semantic Scholar) | ✅ Working |
| PDF download + parse (PyMuPDF) | ✅ Working |
| Chunk + embed + FAISS index | ✅ Working |
| Hybrid retrieval (vector + FTS5 + RRF) | ✅ Working |
| Single-paper analysis | ✅ Working |
| 5 Claude Code skills | ✅ Working |
| Global install / uninstall / toggle | ✅ Working |
| Multi-paper comparison | 🔜 Planned |
| Literature review generation | 🔜 Planned |
| GROBID integration | 🔜 Planned |

### Known limitations

- PDF parsing works best with text-based PDFs (arXiv-quality). Scanned/image PDFs are not yet supported.
- First MCP tool call has a cold-start delay (~2-3s) while the Python process loads.
- Embedding model (`all-MiniLM-L6-v2`) is English-optimized. Non-English papers may have lower retrieval quality.
- No Windows testing yet. macOS and Linux are the primary platforms.

---

## MCP Tools

### Ingest Server

| Tool | Description |
|------|-------------|
| `search_papers` | Search arXiv + Semantic Scholar with deduplication |
| `fetch_pdf` | Download a PDF without triggering the full pipeline |
| `ingest_paper` | Full pipeline: download → parse → chunk → embed → index |
| `batch_ingest` | Batch ingest up to 100 papers |
| `get_ingest_status` | Check job or paper processing status |

### Retrieval Server

| Tool | Description |
|------|-------------|
| `retrieve_evidence` | Hybrid search (vector + full-text + RRF ranking) with metadata filters |

---

## Documentation

| Doc | Description |
|-----|-------------|
| [Architecture](docs/01_architecture_and_boundaries.md) | Four-layer design, data flow, extension mechanisms |
| [Schema & Tool Contracts](docs/02_schema_and_tool_contracts.md) | Data models, state machine, MCP tool interfaces |
| [Claude Code Adaptation](docs/03_claude_code_adaptation.md) | Skills, agents, hooks, CLAUDE.md design |
| [Implementation Plan](docs/04_implementation_plan.md) | Sprint breakdown, test strategy, risk mitigation |
| [Fork & Adapt Guide](docs/fork-guide.md) | How to repurpose this for patents, legal, finance, etc. |
| [Configuration](docs/configuration.md) | Embedding models, LLM setup, environment variables |
| [FAQ](docs/faq.md) | Common questions about safety, scope, and alternatives |

---

## Contributing

Contributions welcome. See [CONTRIBUTING.md](CONTRIBUTING.md).

If you've adapted this for another domain, open an issue to share.

## License

[MIT](LICENSE)

---


