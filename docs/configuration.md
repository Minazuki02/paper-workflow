# Configuration

## Model Configuration

Paper Workflow doesn't lock you into any specific model. Configure via `.env` in the project root.

### Embedding Models

| Setup | Model | Notes |
|-------|-------|-------|
| Local (default) | `all-MiniLM-L6-v2` via sentence-transformers | Free, no API key needed, English-optimized |
| API | Any OpenAI-compatible embedding API | Set `EMBEDDING_API_URL` and `EMBEDDING_API_KEY` in `.env` |

### LLM for Analysis

| Setup | Notes |
|-------|-------|
| CC's built-in model (default) | Uses Claude Code's own model for analysis. No extra cost. |
| External API | Set `LLM_API_URL`, `LLM_API_KEY`, `LLM_MODEL` in `.env`. Supports GLM, Qwen, GPT, etc. |

### Recommended Configurations

| Use case | Embedding | LLM | Cost |
|----------|-----------|-----|------|
| Quick start / evaluation | Local sentence-transformers | CC's built-in | Free |
| Better multilingual support | OpenAI-compatible API | CC's built-in | Low |
| Full API mode | OpenAI-compatible API | External LLM API | Pay per use |

## Environment Variables

Copy `.env.example` to `.env` and edit as needed:

```bash
cp .env.example .env
```

Key variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `PAPER_WORKFLOW_DATA_DIR` | `./data` | Where PDFs, database, and index are stored |
| `EMBEDDING_MODEL` | `all-MiniLM-L6-v2` | Local embedding model name |
| `EMBEDDING_API_URL` | (empty) | OpenAI-compatible embedding endpoint |
| `EMBEDDING_API_KEY` | (empty) | API key for embedding endpoint |
| `LLM_API_URL` | (empty) | OpenAI-compatible LLM endpoint |
| `LLM_API_KEY` | (empty) | API key for LLM endpoint |
| `LLM_MODEL` | (empty) | Model name for analysis LLM |

## Data Directory

All runtime data is stored under `PAPER_WORKFLOW_DATA_DIR`:

```
data/
├── pdfs/    # Downloaded PDF files
├── db/      # SQLite database (metadata + FTS)
├── index/   # FAISS vector index
├── cache/   # Parsing intermediate cache
└── logs/    # Structured JSON logs
```

This directory is gitignored. Your paper data persists across disable/enable toggles and is only deleted if you explicitly choose to during `uninstall.sh`.
