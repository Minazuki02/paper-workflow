# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/).

## [0.1.0-alpha] - 2025-04-13

### Added
- Multi-source academic paper search (arXiv + Semantic Scholar) with deduplication
- Full ingest pipeline: PDF download → PyMuPDF parsing → metadata extraction → section detection → chunk splitting → embedding → FAISS + SQLite indexing
- Hybrid retrieval: vector search (FAISS) + full-text search (SQLite FTS5) + Reciprocal Rank Fusion
- LLM-driven single-paper analysis (Summary, Contributions, Methodology, Key Findings, Limitations)
- 2 MCP Servers (Ingest + Retrieval) with 6 tools total
- 5 Claude Code skills: `/paper-search`, `/paper-ingest`, `/paper-evidence`, `/paper-analyze`, `/paper-status`
- 1 Claude Code agent: batch ingest operator
- 3 rule sets: paper routing, output format, error handling
- Configurable embedding (local sentence-transformers or any OpenAI-compatible API)
- Configurable LLM (any OpenAI-compatible API)
- Paper state machine with 12 states and retry logic
- 140+ test cases across unit, contract, integration, and quality layers
