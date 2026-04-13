# Paper Workflow
<img width="1536" height="1024" alt="a3e7f7b86b1225a26e8b1379ee10620d" src="https://github.com/user-attachments/assets/b64ccfb1-ea0a-4136-90b5-ab92e4533910" />

> Turn Claude Code into a research assistant. Install in one command, remove in one command. Zero residue.

[![Python](https://img.shields.io/badge/Python-≥3.11-3776AB?logo=python&logoColor=white)](https://python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![MCP](https://img.shields.io/badge/Protocol-MCP-8A2BE2)](https://modelcontextprotocol.io)
[![Tests](https://img.shields.io/badge/tests-140%2B-brightgreen)]()

<!-- TODO: replace with actual terminal recording
[![Demo](https://img.shields.io/badge/▶_Watch_Demo-30s-blue)]()
-->

**Paper Workflow** is a fully removable plugin for [Claude Code](https://docs.anthropic.com/en/docs/claude-code). It adds academic paper search, ingestion, retrieval, and analysis — without touching CC source code, without locking you in, and without breaking your coding workflow.

```
Install:    bash scripts/install.sh       → paper tools available everywhere
Disable:    bash scripts/paper-workflow.sh disable  → pure coding mode, instant
Re-enable:  bash scripts/paper-workflow.sh enable   → paper tools back, instant
Uninstall:  bash scripts/uninstall.sh     → gone, zero traces in ~/.claude/
```

### What it does

```
you: /paper-search "LLM agent reasoning 2024"
 CC: Found 20 papers across arXiv + Semantic Scholar…

you: /paper-ingest 1,3,5
 CC: 3 papers downloaded, parsed, embedded, and indexed ✓

you: What attention variants exist in the literature?
 CC: Based on 8 evidence chunks from your library:
     > "Multi-head attention allows the model to jointly attend…"
     > — Attention Is All You Need (Vaswani et al., 2017), §3.2, p.4, score: 0.87

you: /paper-analyze <paper-id>
 CC: ## Summary
     This paper introduces the Transformer architecture…
     ## Key Findings  [3 evidence refs]
     ## Limitations   [2 evidence refs]
```

Every claim is backed by a direct quote from the actual PDF you ingested — not the model's training data.

---

## Why this project?

| Pain point | Without Paper Workflow | With Paper Workflow |
|---|---|---|
| Finding papers | Open browser, search manually | `/paper-search` across arXiv + Semantic Scholar |
| Reading PDFs | Read 30 pages yourself | Ingest → structured chunks → instant retrieval |
| "What does the literature say?" | LLM guesses from training data | Retrieves exact quotes with page numbers |
| Verifying claims | No source, no confidence | Every answer includes paper title, section, page, score |
| Building a knowledge base | Scattered notes | Persistent local library with vector + full-text search |
| **Worried it breaks CC?** | — | **Disable in 1 second, uninstall in 1 command. Zero residue.** |

**Claude Code is the best AI coding tool. This project makes it the best AI research tool too — in the same terminal.**

<details>
<summary><strong>Q: Won't this mess up my CC setup?</strong></summary>

No. Install and uninstall are fully reversible:
- `install.sh` writes a manifest of every file it creates
- `uninstall.sh` reads that manifest and removes exactly those files
- Your existing `~/.claude/settings.json` is merged, not replaced — and cleanly restored on uninstall
- `disable` / `enable` toggles in < 1 second without touching your data

If anything goes wrong, `bash scripts/uninstall.sh` is always a clean exit.
</details>

<details>
<summary><strong>Q: Why not a standalone app?</strong></summary>

CC already solves the hard parts: natural language understanding, multi-step reasoning, tool orchestration. We only add the missing paper capabilities. When you finish analyzing papers, you can immediately ask CC to write code based on what you learned — in the same session.
</details>

<details>
<summary><strong>Q: How is this different from asking ChatGPT to summarize a paper?</strong></summary>

ChatGPT answers from training data. Paper Workflow answers from PDFs you actually ingested. Every evidence chunk links back to a specific paper, section, and page number. No hallucinated citations.
</details>

---

## Quick Start

### Install

```bash
git clone https://github.com/Minazuki02/paper-workflow.git
cd paper-workflow
bash scripts/install.sh
```

The install script:
1. Checks Python ≥ 3.11 and installs the backend package
2. Injects skills, agents, rules, and MCP server config into `~/.claude/`
3. Writes a manifest (`~/.claude/.paper-workflow-manifest.json`) tracking every injected file

Now start Claude Code **from any directory** — paper tools are globally available:

```bash
claude
# Try: /paper-search "transformer attention"
```

> **Requirements:** [Claude Code](https://docs.anthropic.com/en/docs/claude-code) installed, `python3` ≥ 3.11 on PATH.
> Verify with: `python3 --version`

### Switch modes

Don't need papers right now? One command to turn it off, one to turn it back on:

```bash
bash scripts/paper-workflow.sh disable   # CC returns to pure coding mode
bash scripts/paper-workflow.sh enable    # Paper tools restored instantly
bash scripts/paper-workflow.sh status    # Check current state
```

Your ingested papers and data are always preserved across toggles.

### Uninstall

Want it completely gone?

```bash
bash scripts/uninstall.sh
```

Reads the install manifest and removes exactly what was added — skills, agents, rules, MCP servers, hooks, permissions. Your `~/.claude/` is restored to its pre-install state. Optionally deletes paper data and the Python package.

<details>
<summary>Model configuration options</summary>

Paper Workflow doesn't lock you into any specific model. Configure via `.env`:

| Setup | Embedding | LLM | Cost |
|-------|-----------|-----|------|
| Local | sentence-transformers | CC's built-in model | Free |
| API | Any OpenAI-compatible API | Any OpenAI-compatible API | Pay per use |
| Hybrid | Local embedding + remote LLM | Your choice | Low cost |

</details>

---

## Current Status

This project is in **early alpha**. The core pipeline works end-to-end, but rough edges exist.

| Feature | Status | Notes |
|---------|--------|-------|
| Multi-source search (arXiv + Semantic Scholar) | ✅ Working | Deduplication, graceful fallback |
| PDF download + parse (PyMuPDF) | ✅ Working | Best with arXiv-quality PDFs |
| Chunk + embed + FAISS index | ✅ Working | Configurable embedding model |
| Hybrid retrieval (vector + FTS5 + RRF) | ✅ Working | |
| Single-paper analysis | ✅ Working | LLM-driven structured output |
| 5 Claude Code skills | ✅ Working | search, ingest, evidence, analyze, status |
| Batch ingest agent | ✅ Working | Background operation with progress tracking |
| **Global install / uninstall / toggle** | ✅ Working | **Manifest-tracked, clean removal** |
| Multi-paper comparison | 🔜 Planned | |
| Literature review generation | 🔜 Planned | |
| GROBID integration | 🔜 Planned | Higher quality PDF parsing |

---

## Architecture

```
┌──────────────────────────────────────┐
│  Claude Code  (unmodified)           │
│  Reads ~/.claude/ on every startup   │
│  ┌────────┐ ┌────────┐ ┌──────────┐ │
│  │ Skills │ │ Agents │ │ Rules    │ │
│  └───┬────┘ └───┬────┘ └────┬─────┘ │
│      └──────────┼───────────┘       │
│            MCP Protocol (stdio)      │
└─────────────────┼────────────────────┘
                  │
┌─────────────────▼────────────────────┐
│  Python Backend  (this project)      │
│  ┌───────────┐  ┌────────────┐      │
│  │  Ingest   │  │ Retrieval  │      │
│  │  Server   │  │ Server     │      │
│  │  5 tools  │  │ 1 tool     │      │
│  └─────┬─────┘  └──────┬─────┘      │
│        └────────┬───────┘            │
│        ┌────────▼────────┐           │
│        │ SQLite + FAISS  │           │
│        │ + PDF storage   │           │
│        └─────────────────┘           │
└──────────────────────────────────────┘
```

**Design principles:**
- CC doesn't touch data. Backend doesn't touch users. MCP bridges the two.
- Everything injected into `~/.claude/` is tracked by a manifest — nothing is left behind on uninstall.
- CC source code is never modified. All capabilities come through the official extension system.

### Built with

| Layer | Technology | Purpose |
|-------|-----------|---------|
| Protocol | [MCP](https://modelcontextprotocol.io) (stdio) | CC ↔ Python backend communication |
| PDF parsing | [PyMuPDF](https://pymupdf.readthedocs.io) | Text extraction, metadata, page mapping |
| Vector search | [FAISS](https://github.com/facebookresearch/faiss) | Similarity search over paper chunks |
| Metadata + FTS | [SQLite](https://sqlite.org) + FTS5 | Structured storage + full-text search |
| Data models | [Pydantic](https://docs.pydantic.dev) v2 | Schema validation (Paper, Chunk, IngestJob…) |
| Embedding | Configurable | Local sentence-transformers or any OpenAI-compatible API |
| Academic search | arXiv API + Semantic Scholar API | Dual-source discovery with deduplication |

All components are replaceable. See [Component Swapping](#component-swapping) below.

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

## For Developers: Fork & Adapt

This project is a **complete reference implementation** of the Claude Code extension system. If you want to build CC-powered workflows for your own domain, fork this repo and change three things:

```
.claude/
├── CLAUDE.md        ← Your domain rules
├── rules/           ← Your routing logic
├── skills/          ← Your user-facing commands
├── agents/          ← Your background task runners
└── settings.json    ← Register your MCP servers

backend/             ← Your domain backend
scripts/
├── install.sh       ← Your global installer (reuse the manifest pattern)
├── uninstall.sh     ← Your clean uninstaller
└── paper-workflow.sh ← Your enable/disable toggle
```

The pattern — `search → ingest → retrieve → analyze` with `install → disable → enable → uninstall` lifecycle — applies to many domains:

- **Patent search & analysis**
- **Legal case retrieval**
- **Internal knowledge base** (wiki → searchable AI assistant)
- **Financial report analysis**
- **Medical literature review**

### CC Extension Mechanisms Used

| Mechanism | Format | What it does | Example in this project |
|-----------|--------|-------------|------------------------|
| CLAUDE.md | Markdown | Injects system-level rules, auto-loaded every session | Paper routing rules, output format constraints |
| Skills | Markdown + frontmatter | User-invokable `/` commands | `/paper-search`, `/paper-ingest` |
| Agents | Markdown + frontmatter | Background task runners with isolated context | Batch ingest operator |
| MCP Server | Any language | Exposes external tools to CC via standard protocol | Python ingest/retrieval servers |

---

## Component Swapping

| Component | Current | Can be replaced with |
|-----------|---------|---------------------|
| PDF parsing | PyMuPDF | GROBID (structured parsing) |
| Vector index | FAISS | Qdrant / Milvus / Chroma |
| Metadata store | SQLite + FTS5 | PostgreSQL |
| Embedding | Configurable | Any OpenAI-compatible API or local model |
| LLM | Configurable | Any OpenAI-compatible API |
| Search sources | arXiv + Semantic Scholar | PubMed / DBLP / Google Scholar |

---

## Project Structure

```
paper-workflow/
├── .claude/                 # CC extension config (pure markdown)
│   ├── CLAUDE.md            # Paper routing rules entry point
│   ├── rules/               # Routing, output format, error handling
│   ├── skills/              # 5 user-facing slash commands
│   ├── agents/              # Background task agents
│   └── settings.json        # MCP server registration + permissions
│
├── backend/                 # Python paper processing backend
│   ├── ingest/              # Ingest MCP Server (download/parse/index)
│   ├── retrieval/           # Retrieval MCP Server (vector+FTS search)
│   ├── search/              # arXiv + Semantic Scholar providers
│   ├── storage/             # SQLite + FAISS + PDF file management
│   ├── analysis/            # LLM-driven paper analysis
│   └── common/              # Data models, config, error codes
│
├── scripts/
│   ├── install.sh           # Global install → ~/.claude/
│   ├── uninstall.sh         # Clean removal (manifest-based)
│   └── paper-workflow.sh    # Enable / disable toggle
│
├── tests/                   # 140+ test cases (unit, contract, integration, quality)
├── docs/                    # Architecture & design documents
└── data/                    # Runtime data (gitignored)
```

---

## Contributing

Contributions are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

If you've adapted this project for another domain, we'd love to hear about it — open an issue to share.

## License

[MIT](LICENSE)

---

<p align="center">
  <a href="README.zh-CN.md">中文版 README</a>
</p>
