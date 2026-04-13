# Fork & Adapt Guide

Paper Workflow is a **complete reference implementation** of the Claude Code extension system. If you want to build CC-powered workflows for your own domain, fork this repo and change three things.

## What to change

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

The pattern — `search → ingest → retrieve → analyze` with `install → disable → enable → uninstall` lifecycle — applies to many domains.

## Suitable domains

- **Patent search & analysis**
- **Legal case retrieval**
- **Internal knowledge base** (wiki → searchable AI assistant)
- **Financial report analysis**
- **Medical literature review**

## CC Extension Mechanisms Used

| Mechanism | Format | What it does | Example in this project |
|-----------|--------|-------------|--------------------------|
| CLAUDE.md | Markdown | Injects system-level rules, auto-loaded every session | Paper routing rules, output format constraints |
| Skills | Markdown + frontmatter | User-invokable `/` commands | `/paper-search`, `/paper-ingest` |
| Agents | Markdown + frontmatter | Background task runners with isolated context | Batch ingest operator |
| MCP Server | Any language | Exposes external tools to CC via standard protocol | Python ingest/retrieval servers |

## Component Swapping

All core components are replaceable without affecting other modules:

| Component | Current | Can be replaced with |
|-----------|---------|---------------------|
| PDF parsing | PyMuPDF | GROBID (structured parsing) |
| Vector index | FAISS | Qdrant / Milvus / Chroma |
| Metadata store | SQLite + FTS5 | PostgreSQL |
| Embedding | Configurable | Any OpenAI-compatible API or local model |
| LLM | Configurable | Any OpenAI-compatible API |
| Search sources | arXiv + Semantic Scholar | PubMed / DBLP / Google Scholar |

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
├── tests/                   # 89 test cases (unit, contract, integration, quality)
├── docs/                    # Architecture & design documents
└── data/                    # Runtime data (gitignored)
```
