"""Vector search over the Phase 1 FAISS chunk index."""

from __future__ import annotations

from backend.ingest.embedder import SentenceTransformerEmbedder
from backend.retrieval.filters import RetrievalFilters, SearchRun, fetch_chunk_records
from backend.storage.faiss_store import FaissStore
from backend.storage.sqlite_store import SQLiteMetadataStore


class VectorSearcher:
    """Run chunk-level vector retrieval and hydrate RetrievalHit metadata."""

    def __init__(
        self,
        *,
        metadata_store: SQLiteMetadataStore | None = None,
        vector_store: FaissStore | None = None,
        embedder: SentenceTransformerEmbedder | None = None,
    ) -> None:
        self._metadata_store = metadata_store or SQLiteMetadataStore()
        self._vector_store = vector_store or FaissStore()
        self._embedder = embedder or SentenceTransformerEmbedder()

    def embed_query(self, query: str) -> list[float]:
        """Convert a user query into an embedding vector."""

        return self._embedder.embed_texts([query])[0]

    def has_index(self) -> bool:
        """Return whether the vector store currently contains any chunks."""

        self._vector_store.load()
        return self._vector_store_size() > 0

    def search(
        self,
        query: str,
        *,
        top_k: int = 10,
        filters: RetrievalFilters | None = None,
        min_score: float = 0.0,
    ) -> SearchRun:
        """Embed the query and return top vector hits."""

        query_vector = self.embed_query(query)
        return self.search_by_vector(
            query_vector,
            top_k=top_k,
            filters=filters,
            min_score=min_score,
        )

    def search_by_vector(
        self,
        query_vector: list[float],
        *,
        top_k: int = 10,
        filters: RetrievalFilters | None = None,
        min_score: float = 0.0,
    ) -> SearchRun:
        """Search the FAISS index using a pre-computed query vector."""

        self._vector_store.load()
        store_size = self._vector_store_size()
        if top_k <= 0 or store_size == 0:
            return SearchRun(hits=[], total_candidates=0)

        candidate_limit = min(store_size, max(top_k * 10, top_k, 50))
        raw_hits = self._vector_store.search(query_vector, top_k=candidate_limit)
        if not raw_hits:
            return SearchRun(hits=[], total_candidates=0)

        chunk_ids = [hit.chunk_id for hit in raw_hits]
        records = {
            record.chunk_id: record
            for record in fetch_chunk_records(
                self._metadata_store.connection,
                filters=filters,
                chunk_ids=chunk_ids,
            )
        }

        candidates = []
        for raw_hit in raw_hits:
            record = records.get(raw_hit.chunk_id)
            if record is None:
                continue
            vector_score = _normalize_vector_score(
                raw_hit.score,
                metric=getattr(self._vector_store, "metric", "cosine"),
            )
            candidates.append(record.to_hit(score=vector_score, vector_score=vector_score))

        final_hits = [hit for hit in candidates if hit.score >= min_score][:top_k]
        return SearchRun(hits=final_hits, total_candidates=len(candidates))

    def _vector_store_size(self) -> int:
        if hasattr(self._vector_store, "size"):
            return int(getattr(self._vector_store, "size"))
        if hasattr(self._vector_store, "vectors"):
            return len(getattr(self._vector_store, "vectors"))
        return 0


def _normalize_vector_score(raw_score: float, *, metric: str) -> float:
    if metric == "l2":
        return 1.0 / (1.0 + max(0.0, float(raw_score)))
    return max(0.0, min(1.0, (float(raw_score) + 1.0) / 2.0))
