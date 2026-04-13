# Contributing to Paper Workflow

Thanks for your interest in contributing!

## Getting Started

```bash
git clone https://github.com/Minazuki02/paper-workflow.git
cd paper-workflow
pip install -e "./backend[dev]"
cp .env.example .env
```

## Running Tests

```bash
# Unit tests (fast, no external dependencies)
python -m pytest tests/unit/ -q

# Contract tests (validates MCP tool schemas)
python -m pytest tests/contract/ -q

# All tests
python -m pytest tests/ -q
```

## Project Structure

- **`.claude/`** — Claude Code extension config (skills, agents, rules). Edit these to change CC behavior.
- **`backend/`** — Python MCP servers. This is where the paper processing logic lives.
- **`tests/`** — Unit, contract, integration, and quality tests.

## What to Contribute

### Good first issues
- Improve PDF parsing for non-arXiv papers
- Add a new search provider (e.g., PubMed, DBLP)
- Improve chunk splitting heuristics
- Add more test fixtures

### Larger contributions
- GROBID integration for structured PDF parsing
- Citation graph extraction
- Multi-paper comparison (`/paper-compare`)

## Code Style

- Python: follow [ruff](https://docs.astral.sh/ruff/) defaults (`ruff check .`)
- Keep functions focused and testable
- Add tests for new functionality

## Pull Requests

1. Fork the repo and create your branch from `main`
2. Add tests for any new functionality
3. Ensure all tests pass
4. Open a PR with a clear description of what changed and why

## Reporting Bugs

Use the [bug report template](https://github.com/Minazuki02/paper-workflow/issues/new?template=bug_report.yml) on GitHub Issues.

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
