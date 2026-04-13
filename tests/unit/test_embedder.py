"""Unit tests for local and remote embedding modes."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from backend.common.config import AppConfig
from backend.common.embeddings import EmbeddingClientError
from backend.ingest.embedder import SentenceTransformerEmbedder


class FakeRemoteEmbeddingClient:
    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    def embed(self, texts: list[str]) -> list[list[float]]:
        self.calls.append(list(texts))
        return [[0.1, 0.2, 0.3] for _ in texts]


class FlakyRemoteEmbeddingClient(FakeRemoteEmbeddingClient):
    def embed(self, texts: list[str]) -> list[list[float]]:
        if len(texts) > 2:
            raise EmbeddingClientError("batch too large")
        return super().embed(texts)


class FakeLocalModel:
    def encode(self, texts, **_: object):
        return [[0.9, 0.8, 0.7] for _ in texts]


def test_embedder_prefers_remote_embedding_provider_when_configured() -> None:
    settings = AppConfig.model_validate(
        {
            "app": {"name": "paper-workflow"},
            "paths": {
                "data_dir": "/tmp/data",
                "logs_dir": "/tmp/data/logs",
                "db_path": "/tmp/data/db/papers.db",
                "index_dir": "/tmp/data/index",
                "pdf_dir": "/tmp/data/pdfs",
            },
            "models": {"embedding_model": "local-model"},
            "embeddings": {
                "api_key": "embed-key",
                "base_url": "https://example.invalid/v1",
                "model": "remote-embedding-model",
                "timeout": 30,
            },
        }
    )
    remote_client = FakeRemoteEmbeddingClient()
    embedder = SentenceTransformerEmbedder(settings=settings, remote_client=remote_client)

    vectors = embedder.embed_texts(["first", "second"])

    assert embedder.model_name == "remote-embedding-model"
    assert remote_client.calls == [["first", "second"]]
    assert vectors == [[0.1, 0.2, 0.3], [0.1, 0.2, 0.3]]


def test_embedder_falls_back_to_local_sentence_transformers() -> None:
    settings = AppConfig.model_validate(
        {
            "app": {"name": "paper-workflow"},
            "paths": {
                "data_dir": "/tmp/data",
                "logs_dir": "/tmp/data/logs",
                "db_path": "/tmp/data/db/papers.db",
                "index_dir": "/tmp/data/index",
                "pdf_dir": "/tmp/data/pdfs",
            },
            "models": {"embedding_model": "local-mini-model"},
        }
    )
    embedder = SentenceTransformerEmbedder(
        settings=settings,
        model_loader=lambda model_name: _assert_model_name(model_name),
    )

    vectors = embedder.embed_texts(["hello world"])

    assert embedder.model_name == "local-mini-model"
    assert vectors == [[0.9, 0.8, 0.7]]


def test_embedder_splits_remote_batches_when_provider_rejects_large_requests() -> None:
    settings = AppConfig.model_validate(
        {
            "app": {"name": "paper-workflow"},
            "paths": {
                "data_dir": "/tmp/data",
                "logs_dir": "/tmp/data/logs",
                "db_path": "/tmp/data/db/papers.db",
                "index_dir": "/tmp/data/index",
                "pdf_dir": "/tmp/data/pdfs",
            },
            "models": {"embedding_model": "local-model"},
            "embeddings": {
                "api_key": "embed-key",
                "base_url": "https://example.invalid/v1",
                "model": "remote-embedding-model",
                "timeout": 30,
            },
        }
    )
    remote_client = FlakyRemoteEmbeddingClient()
    embedder = SentenceTransformerEmbedder(settings=settings, batch_size=4, remote_client=remote_client)

    vectors = embedder.embed_texts(["a", "b", "c", "d"])

    assert vectors == [[0.1, 0.2, 0.3]] * 4
    assert remote_client.calls == [["a", "b"], ["c", "d"]]


def _assert_model_name(model_name: str) -> FakeLocalModel:
    assert model_name == "local-mini-model"
    return FakeLocalModel()
