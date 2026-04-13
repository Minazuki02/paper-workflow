"""OpenAI-compatible embedding client utilities."""

from __future__ import annotations

import json
from typing import Any
from urllib import error as urllib_error
from urllib import request as urllib_request

from backend.common.config import AppConfig, EmbeddingSettings, load_settings


class EmbeddingClientError(RuntimeError):
    """Raised when a configured embedding request cannot be completed."""


class OpenAICompatibleEmbeddingClient:
    """Minimal embeddings client for OpenAI-compatible providers."""

    def __init__(self, settings: AppConfig | EmbeddingSettings | None = None) -> None:
        if isinstance(settings, AppConfig):
            embedding_settings = settings.embeddings
        else:
            embedding_settings = settings or load_settings().embeddings

        if not embedding_settings.configured:
            raise EmbeddingClientError("Embedding provider is not fully configured.")

        self._settings = embedding_settings

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []

        payload = {
            "model": self._settings.model,
            "input": texts,
        }
        response = self._post_json(payload)
        return _extract_embeddings(response, expected_count=len(texts))

    def _post_json(self, payload: dict[str, Any]) -> dict[str, Any]:
        endpoint = f"{self._settings.base_url.rstrip('/')}/embeddings"
        body = json.dumps(payload).encode("utf-8")
        req = urllib_request.Request(
            endpoint,
            data=body,
            method="POST",
            headers={
                "Authorization": f"Bearer {self._settings.api_key}",
                "Content-Type": "application/json",
            },
        )

        try:
            with urllib_request.urlopen(req, timeout=self._settings.timeout) as response:
                charset = response.headers.get_content_charset("utf-8")
                raw_body = response.read().decode(charset)
        except urllib_error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise EmbeddingClientError(
                f"Embedding request failed with HTTP {exc.code}: {detail}"
            ) from exc
        except urllib_error.URLError as exc:
            raise EmbeddingClientError(f"Embedding request failed: {exc.reason}") from exc
        except TimeoutError as exc:
            raise EmbeddingClientError("Embedding request timed out.") from exc

        try:
            decoded = json.loads(raw_body)
        except json.JSONDecodeError as exc:
            raise EmbeddingClientError("Embedding response was not valid JSON.") from exc

        if "error" in decoded:
            raise EmbeddingClientError(f"Embedding provider returned an error: {decoded['error']}")

        return decoded


def _extract_embeddings(payload: dict[str, Any], *, expected_count: int) -> list[list[float]]:
    data = payload.get("data")
    if not isinstance(data, list) or not data:
        raise EmbeddingClientError("Embedding response did not include data.")

    vectors: list[list[float]] = []
    for item in data:
        if not isinstance(item, dict):
            raise EmbeddingClientError("Embedding item format was invalid.")
        embedding = item.get("embedding")
        if not isinstance(embedding, list) or not embedding:
            raise EmbeddingClientError("Embedding item did not include a valid vector.")
        vectors.append([float(value) for value in embedding])

    if len(vectors) != expected_count:
        raise EmbeddingClientError("Embedding response count did not match request count.")
    return vectors
