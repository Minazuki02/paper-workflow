"""Configuration loading tests for .env-backed LLM settings."""

from __future__ import annotations

import textwrap
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from backend.common.config import load_settings


def test_load_settings_reads_llm_values_from_dotenv(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        textwrap.dedent(
            """
            app:
              name: test-app
            paths:
              data_dir: ./data
              logs_dir: ./data/logs
              db_path: ./data/db/papers.db
              index_dir: ./data/index
              pdf_dir: ./data/pdfs
            models:
              embedding_model: all-MiniLM-L6-v2
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )

    dotenv_path = tmp_path / ".env"
    dotenv_path.write_text(
        textwrap.dedent(
            """
            LLM_API_KEY=test-key
            LLM_BASE_URL=https://example.invalid/v2
            LLM_MODEL=test-model
            LLM_TIMEOUT=42
            PAPER_WORKFLOW_LLM_QUERY_REWRITE=true
            EMBEDDING_API_KEY=embed-key
            EMBEDDING_BASE_URL=https://embed.example.invalid/v1
            EMBEDDING_MODEL=embed-model
            EMBEDDING_TIMEOUT=24
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )

    settings = load_settings(
        config_path=config_path,
        env={"PAPER_WORKFLOW_DOTENV_PATH": str(dotenv_path)},
    )

    assert settings.llm.api_key == "test-key"
    assert settings.llm.base_url == "https://example.invalid/v2"
    assert settings.llm.model == "test-model"
    assert settings.llm.timeout == 42
    assert settings.llm.query_rewrite_enabled is True
    assert settings.embeddings.api_key == "embed-key"
    assert settings.embeddings.base_url == "https://embed.example.invalid/v1"
    assert settings.embeddings.model == "embed-model"
    assert settings.embeddings.timeout == 24
