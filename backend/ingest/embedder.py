"""Chunk embedding generator for Phase 1 ingest and retrieval."""

from __future__ import annotations

import importlib
from collections.abc import Sequence
from typing import Any

from backend.common.embeddings import EmbeddingClientError, OpenAICompatibleEmbeddingClient
from backend.common.config import AppConfig, load_settings
from backend.common.errors import EMBED_MODEL_UNAVAILABLE, EMBED_OOM
from backend.common.models import Chunk

DEFAULT_EMBED_BATCH_SIZE = 64


class EmbedderError(RuntimeError):
    """Raised when embedding generation fails with a mapped backend error code."""

    def __init__(self, error_code: str, message: str) -> None:
        super().__init__(message)
        self.error_code = error_code


class SentenceTransformerEmbedder:
    """Generate embeddings using a configured remote provider or local sentence-transformers."""

    def __init__(
        self,
        settings: AppConfig | None = None,
        *,
        model_name: str | None = None,
        batch_size: int = DEFAULT_EMBED_BATCH_SIZE,
        model_loader: Any | None = None,
        remote_client: OpenAICompatibleEmbeddingClient | None = None,
    ) -> None:
        self._settings = settings or load_settings()
        self._model_name = model_name or self._default_model_name()
        self._batch_size = batch_size
        self._model_loader = model_loader
        self._remote_client = remote_client
        self._model: Any | None = None

    @property
    def model_name(self) -> str:
        return self._model_name

    def embed_chunks(self, chunks: Sequence[Chunk]) -> list[list[float]]:
        """Generate embeddings for a list of chunks without mutating MCP-visible models."""

        if not chunks:
            return []

        texts = [self._require_non_empty_text(chunk.text, context=chunk.chunk_id) for chunk in chunks]
        return self.embed_texts(texts)

    def embed_texts(self, texts: Sequence[str]) -> list[list[float]]:
        """Generate embeddings for raw text inputs."""

        if not texts:
            return []

        cleaned_texts = [self._require_non_empty_text(text, context=str(index)) for index, text in enumerate(texts)]

        if self._settings.embeddings.configured:
            return self._embed_texts_remotely(cleaned_texts)

        return self._embed_texts_locally(cleaned_texts)

    def _embed_texts_remotely(self, texts: Sequence[str]) -> list[list[float]]:
        client = self._remote_client or OpenAICompatibleEmbeddingClient(self._settings)
        vectors: list[list[float]] = []
        try:
            for batch in _batched(texts, self._batch_size):
                vectors.extend(self._embed_remote_batch(client, list(batch)))
        except EmbeddingClientError as exc:
            raise EmbedderError(
                EMBED_MODEL_UNAVAILABLE,
                f"Embedding generation failed for model '{self._model_name}'.",
            ) from exc
        return vectors

    def _embed_remote_batch(
        self,
        client: OpenAICompatibleEmbeddingClient,
        texts: list[str],
    ) -> list[list[float]]:
        try:
            return client.embed(texts)
        except EmbeddingClientError:
            if len(texts) == 1:
                raise
            midpoint = max(1, len(texts) // 2)
            return self._embed_remote_batch(client, texts[:midpoint]) + self._embed_remote_batch(
                client,
                texts[midpoint:],
            )

    def _embed_texts_locally(self, texts: Sequence[str]) -> list[list[float]]:
        try:
            encoded = self._get_model().encode(
                list(texts),
                batch_size=self._batch_size,
                show_progress_bar=False,
                convert_to_numpy=True,
            )
        except MemoryError as exc:
            raise EmbedderError(EMBED_OOM, "Embedding generation ran out of memory.") from exc
        except Exception as exc:  # pragma: no cover - depends on model runtime
            raise EmbedderError(
                EMBED_MODEL_UNAVAILABLE,
                f"Embedding generation failed for model '{self._model_name}'.",
            ) from exc

        rows = encoded.tolist() if hasattr(encoded, "tolist") else encoded
        vectors = [[float(value) for value in row] for row in rows]

        if len(vectors) != len(texts):
            raise RuntimeError("Embedding model returned a mismatched number of vectors.")
        if any(len(vector) == 0 for vector in vectors):
            raise RuntimeError("Embedding model returned an empty vector.")

        return vectors

    def _default_model_name(self) -> str:
        if self._settings.embeddings.configured and self._settings.embeddings.model:
            return self._settings.embeddings.model
        return self._settings.models.embedding_model

    def _get_model(self) -> Any:
        if self._model is None:
            self._model = self._load_model()
        return self._model

    def _load_model(self) -> Any:
        try:
            if self._model_loader is not None:
                return self._model_loader(self._model_name)

            module = importlib.import_module("sentence_transformers")
            model_class = getattr(module, "SentenceTransformer")
            return model_class(self._model_name)
        except MemoryError as exc:
            raise EmbedderError(EMBED_OOM, "Loading the embedding model exhausted memory.") from exc
        except Exception as exc:  # pragma: no cover - depends on environment
            raise EmbedderError(
                EMBED_MODEL_UNAVAILABLE,
                f"Embedding model '{self._model_name}' is unavailable.",
            ) from exc

    def _require_non_empty_text(self, text: str, *, context: str) -> str:
        cleaned = text.strip()
        if not cleaned:
            raise ValueError(f"Embedding input is empty for item {context}.")
        return cleaned


def _batched(values: Sequence[str], batch_size: int) -> Sequence[Sequence[str]]:
    return [values[index : index + batch_size] for index in range(0, len(values), batch_size)]
