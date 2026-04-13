"""Optional LLM-backed query rewriting for retrieval requests."""

from __future__ import annotations

from backend.common.config import AppConfig, load_settings
from backend.common.llm import ChatMessage, LLMClientError, OpenAICompatibleLLMClient

REWRITE_SYSTEM_PROMPT = """You rewrite academic retrieval queries.

Return exactly one concise retrieval query.
Rules:
- Keep domain-specific terms, model names, dataset names, and metrics.
- Remove filler words and conversational phrasing.
- Do not explain your answer.
- Do not add quotation marks.
- Do not invent entities that are not implied by the input.
"""


class RetrievalQueryRewriter:
    """Rewrite natural-language questions into tighter retrieval queries."""

    def __init__(
        self,
        settings: AppConfig | None = None,
        *,
        client: OpenAICompatibleLLMClient | None = None,
        max_tokens: int = 96,
    ) -> None:
        self._settings = settings or load_settings()
        self._client = client
        self._max_tokens = max_tokens

    @property
    def enabled(self) -> bool:
        return self._settings.llm.query_rewrite_enabled and self._settings.llm.configured

    def rewrite(self, query: str) -> str:
        if not self.enabled:
            return query

        client = self._client or OpenAICompatibleLLMClient(self._settings)

        try:
            rewritten = client.complete(
                messages=[
                    ChatMessage(role="system", content=REWRITE_SYSTEM_PROMPT),
                    ChatMessage(role="user", content=query),
                ],
                temperature=0.0,
                max_tokens=self._max_tokens,
            )
        except LLMClientError:
            return query

        normalized = " ".join(rewritten.split())
        return normalized or query
