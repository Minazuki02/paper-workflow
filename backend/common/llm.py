"""OpenAI-compatible LLM client utilities for optional backend intelligence."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from urllib import error as urllib_error
from urllib import request as urllib_request

from backend.common.config import AppConfig, LLMSettings, load_settings


class LLMClientError(RuntimeError):
    """Raised when a configured LLM request cannot be completed."""


@dataclass(frozen=True)
class ChatMessage:
    role: str
    content: str


class OpenAICompatibleLLMClient:
    """Minimal chat-completions client for OpenAI-compatible providers."""

    def __init__(self, settings: AppConfig | LLMSettings | None = None) -> None:
        if isinstance(settings, AppConfig):
            llm_settings = settings.llm
        else:
            llm_settings = settings or load_settings().llm

        if not llm_settings.configured:
            raise LLMClientError("LLM is not fully configured.")

        self._settings = llm_settings

    def complete(
        self,
        *,
        messages: list[ChatMessage],
        temperature: float = 0.0,
        max_tokens: int = 256,
    ) -> str:
        payload = {
            "model": self._settings.model,
            "messages": [message.__dict__ for message in messages],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        response = self._post_json(payload)
        return _extract_content(response)

    def _post_json(self, payload: dict[str, Any]) -> dict[str, Any]:
        endpoint = f"{self._settings.base_url.rstrip('/')}/chat/completions"
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
            raise LLMClientError(f"LLM request failed with HTTP {exc.code}: {detail}") from exc
        except urllib_error.URLError as exc:
            raise LLMClientError(f"LLM request failed: {exc.reason}") from exc
        except TimeoutError as exc:
            raise LLMClientError("LLM request timed out.") from exc

        try:
            decoded = json.loads(raw_body)
        except json.JSONDecodeError as exc:
            raise LLMClientError("LLM response was not valid JSON.") from exc

        if "error" in decoded:
            raise LLMClientError(f"LLM provider returned an error: {decoded['error']}")

        return decoded


def _extract_content(payload: dict[str, Any]) -> str:
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        raise LLMClientError("LLM response did not include choices.")

    first_choice = choices[0]
    if not isinstance(first_choice, dict):
        raise LLMClientError("LLM response choice format was invalid.")

    message = first_choice.get("message")
    if not isinstance(message, dict):
        raise LLMClientError("LLM response did not include a message payload.")

    content = message.get("content")
    if isinstance(content, str):
        return content.strip()

    if isinstance(content, list):
        text_parts: list[str] = []
        for part in content:
            if isinstance(part, dict) and part.get("type") == "text" and isinstance(part.get("text"), str):
                text_parts.append(part["text"])
        if text_parts:
            return "\n".join(text_parts).strip()

    raise LLMClientError("LLM response did not include text content.")
