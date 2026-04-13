"""LLM-backed single-paper analysis without introducing a Phase 1 analysis MCP server."""

from __future__ import annotations

import json
from dataclasses import dataclass
from time import perf_counter
from typing import Any

from backend.common.config import AppConfig, load_settings
from backend.common.errors import ANALYZE_LLM_ERROR, ANALYZE_PAPER_NOT_FOUND, ANALYZE_PAPER_NOT_READY
from backend.common.llm import ChatMessage, LLMClientError, OpenAICompatibleLLMClient
from backend.common.models import AnalysisResult, Chunk, Evidence, Paper, RetrievalHit
from backend.ingest.embedder import SentenceTransformerEmbedder
from backend.retrieval.query_rewriter import RetrievalQueryRewriter
from backend.retrieval.tools import handle_retrieve_evidence
from backend.storage.faiss_store import FaissStore
from backend.storage.sqlite_store import SQLiteMetadataStore

DEFAULT_ANALYSIS_TOP_K = 4
MAX_EVIDENCE_SNIPPETS = 12


class SinglePaperAnalysisError(RuntimeError):
    """Raised when single-paper analysis cannot be completed."""

    def __init__(self, error_code: str, message: str) -> None:
        super().__init__(message)
        self.error_code = error_code


@dataclass(frozen=True)
class SinglePaperAnalysisMetrics:
    retrieval_queries: int
    evidence_hits: int
    llm_duration_ms: int
    total_duration_ms: int


@dataclass(frozen=True)
class SinglePaperAnalysisResponse:
    result: AnalysisResult
    metrics: SinglePaperAnalysisMetrics


class SinglePaperAnalyzer:
    """Analyze a ready paper by retrieving evidence and synthesizing with a configured LLM."""

    def __init__(
        self,
        settings: AppConfig | None = None,
        *,
        metadata_store: SQLiteMetadataStore | None = None,
        vector_store: FaissStore | None = None,
        embedder: SentenceTransformerEmbedder | None = None,
        llm_client: OpenAICompatibleLLMClient | None = None,
        query_rewriter: RetrievalQueryRewriter | None = None,
    ) -> None:
        self._settings = settings or load_settings()
        self._metadata_store = metadata_store or SQLiteMetadataStore()
        self._vector_store = vector_store or FaissStore(settings=self._settings)
        self._embedder = embedder or SentenceTransformerEmbedder(settings=self._settings)
        self._llm_client = llm_client
        self._query_rewriter = query_rewriter

    def analyze(
        self,
        *,
        paper_id: str,
        focus: str | None = None,
        user_query: str | None = None,
        top_k_per_query: int = DEFAULT_ANALYSIS_TOP_K,
    ) -> SinglePaperAnalysisResponse:
        started_at = perf_counter()

        paper = self._metadata_store.get_paper(paper_id)
        if paper is None:
            raise SinglePaperAnalysisError(ANALYZE_PAPER_NOT_FOUND, f"paper_id not found: {paper_id}")
        if paper.status != "ready":
            raise SinglePaperAnalysisError(
                ANALYZE_PAPER_NOT_READY,
                f"paper_id {paper_id} is not ready for analysis (status={paper.status}).",
            )

        evidence_hits, retrieval_queries = self._collect_evidence_hits(
            paper=paper,
            focus=focus,
            user_query=user_query,
            top_k_per_query=top_k_per_query,
        )
        if not evidence_hits:
            evidence_hits = self._fallback_hits_from_chunks(paper)

        llm_client = self._llm_client or OpenAICompatibleLLMClient(self._settings)

        llm_started_at = perf_counter()
        try:
            completion = llm_client.complete(
                messages=self._analysis_messages(paper=paper, focus=focus, user_query=user_query, hits=evidence_hits),
                temperature=0.1,
                max_tokens=1400,
            )
        except LLMClientError as exc:
            raise SinglePaperAnalysisError(ANALYZE_LLM_ERROR, str(exc)) from exc
        llm_duration_ms = _elapsed_ms(llm_started_at)

        parsed = _parse_analysis_json(completion)
        result = AnalysisResult(
            task_id=f"single-paper-analysis:{paper.paper_id}",
            paper_id=paper.paper_id,
            summary=str(parsed["summary"]).strip(),
            contributions=_normalize_str_list(parsed.get("contributions")),
            methodology=str(parsed["methodology"]).strip(),
            key_findings=_normalize_str_list(parsed.get("key_findings")),
            limitations=_normalize_str_list(parsed.get("limitations")),
            future_work=_normalize_str_list(parsed.get("future_work")),
            evidence=_hits_to_evidence(evidence_hits),
            model_used=self._settings.llm.model or "unknown",
            token_cost=None,
        )
        metrics = SinglePaperAnalysisMetrics(
            retrieval_queries=retrieval_queries,
            evidence_hits=len(evidence_hits),
            llm_duration_ms=llm_duration_ms,
            total_duration_ms=_elapsed_ms(started_at),
        )
        return SinglePaperAnalysisResponse(result=result, metrics=metrics)

    def _collect_evidence_hits(
        self,
        *,
        paper: Paper,
        focus: str | None,
        user_query: str | None,
        top_k_per_query: int,
    ) -> tuple[list[RetrievalHit], int]:
        hits_by_chunk_id: dict[str, RetrievalHit] = {}
        retrieval_queries = 0

        for query_text, section_types in _build_analysis_queries(paper=paper, focus=focus, user_query=user_query):
            retrieval_queries += 1
            result = handle_retrieve_evidence(
                query=query_text,
                top_k=top_k_per_query,
                paper_ids=[paper.paper_id],
                section_types=section_types,
                search_mode="hybrid",
                min_score=0.2,
                metadata_store=self._metadata_store,
                vector_store=self._vector_store,
                embedder=self._embedder,
                query_rewriter=self._query_rewriter,
            )
            if result.get("error") is True:
                continue

            for payload in result.get("hits", []):
                hit = RetrievalHit.model_validate(payload)
                existing = hits_by_chunk_id.get(hit.chunk_id)
                if existing is None or hit.score > existing.score:
                    hits_by_chunk_id[hit.chunk_id] = hit

        ranked_hits = sorted(
            hits_by_chunk_id.values(),
            key=lambda hit: (-hit.score, hit.paper_title, hit.chunk_id),
        )
        return ranked_hits[:MAX_EVIDENCE_SNIPPETS], retrieval_queries

    def _fallback_hits_from_chunks(self, paper: Paper) -> list[RetrievalHit]:
        chunks = self._metadata_store.get_chunks(paper.paper_id)
        if not chunks:
            return []

        selected = _select_analysis_chunks(chunks)[:MAX_EVIDENCE_SNIPPETS]
        authors = ", ".join(author.name for author in paper.authors)
        return [
            RetrievalHit(
                chunk_id=chunk.chunk_id,
                paper_id=chunk.paper_id,
                text=chunk.text,
                score=0.3,
                vector_score=None,
                text_score=None,
                paper_title=paper.title,
                authors=authors,
                year=paper.year,
                section_type=chunk.section_type,
                heading=chunk.heading,
                page_start=chunk.page_start,
                highlights=None,
            )
            for chunk in selected
        ]

    def _analysis_messages(
        self,
        *,
        paper: Paper,
        focus: str | None,
        user_query: str | None,
        hits: list[RetrievalHit],
    ) -> list[ChatMessage]:
        focus_text = focus or "balanced full-paper analysis"
        user_prompt = user_query or ""
        evidence_payload = [
            {
                "chunk_id": hit.chunk_id,
                "score": hit.score,
                "section_type": hit.section_type,
                "heading": hit.heading,
                "page_start": hit.page_start,
                "text": hit.text,
            }
            for hit in hits
        ]

        return [
            ChatMessage(
                role="system",
                content=(
                    "You are an academic paper analysis assistant. "
                    "Return valid JSON only with keys: summary, contributions, methodology, "
                    "key_findings, limitations, future_work."
                ),
            ),
            ChatMessage(
                role="user",
                content=json.dumps(
                    {
                        "paper": {
                            "paper_id": paper.paper_id,
                            "title": paper.title,
                            "authors": [author.model_dump() for author in paper.authors],
                            "abstract": paper.abstract,
                            "year": paper.year,
                            "venue": paper.venue,
                        },
                        "analysis_focus": focus_text,
                        "user_query": user_prompt,
                        "required_output_order": [
                            "summary",
                            "contributions",
                            "methodology",
                            "key_findings",
                            "limitations",
                            "future_work",
                        ],
                        "instructions": [
                            "Base every conclusion on the provided evidence snippets.",
                            "If evidence is insufficient for a section, say so explicitly.",
                            "Keep contributions, key_findings, limitations, and future_work concise.",
                            "Use plain strings only. contributions, key_findings, limitations, and future_work must be arrays of strings.",
                        ],
                        "evidence": evidence_payload,
                    },
                    ensure_ascii=False,
                ),
            ),
        ]


def _build_analysis_queries(
    *,
    paper: Paper,
    focus: str | None,
    user_query: str | None,
) -> list[tuple[str, list[str] | None]]:
    title_context = paper.title
    queries: list[tuple[str, list[str] | None]] = [
        (f"{title_context} main contribution novelty", ["introduction", "conclusion"]),
        (f"{title_context} methodology approach model method", ["methodology"]),
        (f"{title_context} experiments results evaluation findings", ["experiments", "discussion", "conclusion"]),
        (f"{title_context} limitations failure cases future work", ["discussion", "conclusion"]),
    ]

    if focus:
        queries.insert(0, (f"{title_context} {focus}", None))
    if user_query:
        queries.insert(0, (user_query, None))

    return queries


def _select_analysis_chunks(chunks: list[Chunk]) -> list[Chunk]:
    preferred_section_order = {
        "abstract": 0,
        "introduction": 1,
        "methodology": 2,
        "experiments": 3,
        "discussion": 4,
        "conclusion": 5,
        "other": 6,
        "appendix": 7,
        "references": 8,
    }
    return sorted(
        chunks,
        key=lambda chunk: (
            preferred_section_order.get(chunk.section_type or "other", 99),
            chunk.order_index,
            chunk.chunk_id,
        ),
    )


def _parse_analysis_json(raw_text: str) -> dict[str, Any]:
    candidate = raw_text.strip()
    if candidate.startswith("```"):
        candidate = candidate.strip("`")
        candidate = candidate.partition("\n")[2].strip()
        if candidate.endswith("```"):
            candidate = candidate[:-3].strip()

    try:
        payload = json.loads(candidate)
    except json.JSONDecodeError:
        start = candidate.find("{")
        end = candidate.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise SinglePaperAnalysisError(ANALYZE_LLM_ERROR, "LLM did not return valid JSON.")
        try:
            payload = json.loads(candidate[start : end + 1])
        except json.JSONDecodeError as exc:
            raise SinglePaperAnalysisError(ANALYZE_LLM_ERROR, "LLM did not return valid analysis JSON.") from exc

    required = {"summary", "contributions", "methodology", "key_findings", "limitations", "future_work"}
    missing = required - set(payload)
    if missing:
        raise SinglePaperAnalysisError(ANALYZE_LLM_ERROR, f"LLM response missing keys: {sorted(missing)}")
    return payload


def _normalize_str_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    normalized = str(value).strip()
    return [] if not normalized else [normalized]


def _hits_to_evidence(hits: list[RetrievalHit]) -> list[Evidence]:
    evidence_items: list[Evidence] = []
    for hit in hits:
        evidence_items.append(
            Evidence(
                claim=_evidence_claim_from_hit(hit),
                text=hit.text,
                chunk_id=hit.chunk_id,
                paper_id=hit.paper_id,
                paper_title=hit.paper_title,
                section_type=hit.section_type,
                confidence=hit.score,
                evidence_type="methodological" if hit.section_type == "methodology" else "qualitative",
                page=hit.page_start,
            )
        )
    return evidence_items


def _evidence_claim_from_hit(hit: RetrievalHit) -> str:
    if hit.section_type == "methodology":
        return "Supports the paper's methodology description."
    if hit.section_type == "experiments":
        return "Supports the paper's key findings or evaluation claims."
    if hit.section_type == "discussion":
        return "Supports the paper's limitations or discussion points."
    if hit.section_type == "conclusion":
        return "Supports the paper's concluding claims."
    return "Supports the paper analysis."


def _elapsed_ms(started_at: float) -> int:
    return max(0, int(round((perf_counter() - started_at) * 1000)))
