"""Minimal FAISS-backed vector index persistence layer."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import numpy as np

from backend.common.config import AppConfig, load_settings

MetricType = Literal["cosine", "l2"]


@dataclass(frozen=True)
class VectorSearchHit:
    chunk_id: str
    score: float


class FaissStore:
    """Manage vector index persistence without embedding-generation concerns."""

    def __init__(
        self,
        settings: AppConfig | None = None,
        *,
        index_name: str = "chunks",
    ) -> None:
        self._settings = settings or load_settings()
        self._index_name = index_name
        self._index_dir = self._settings.paths.index_dir
        self._index_dir.mkdir(parents=True, exist_ok=True)
        self._faiss = _load_faiss()
        self._index = None
        self._dimension: int | None = None
        self._metric: MetricType = "cosine"
        self._id_map: dict[int, str] = {}
        self._next_internal_id = 0

    @property
    def index_path(self) -> Path:
        return self._index_dir / f"{self._index_name}.faiss"

    @property
    def metadata_path(self) -> Path:
        return self._index_dir / f"{self._index_name}.meta.json"

    @property
    def dimension(self) -> int | None:
        return self._dimension

    @property
    def metric(self) -> MetricType:
        return self._metric

    @property
    def size(self) -> int:
        return len(self._id_map)

    def create(self, dimension: int, *, metric: MetricType = "cosine") -> None:
        """Create a new empty index with the requested vector dimension."""

        if dimension <= 0:
            raise ValueError("FAISS index dimension must be greater than zero.")

        self._dimension = dimension
        self._metric = metric
        self._index = self._new_index(dimension, metric)
        self._id_map = {}
        self._next_internal_id = 0

    def add(self, chunk_ids: list[str], vectors: list[list[float]] | np.ndarray) -> None:
        """Append vectors to the index, creating it on first use when needed."""

        if len(chunk_ids) == 0:
            return

        matrix = self._as_matrix(vectors)
        self._ensure_index(matrix.shape[1])

        if len(chunk_ids) != matrix.shape[0]:
            raise ValueError("The number of chunk ids must match the number of vectors.")

        internal_ids = np.empty(len(chunk_ids), dtype=np.int64)
        for position, chunk_id in enumerate(chunk_ids):
            internal_id = self._next_internal_id
            self._next_internal_id += 1
            self._id_map[internal_id] = chunk_id
            internal_ids[position] = internal_id

        prepared = self._prepare_vectors(matrix)
        self._index.add_with_ids(prepared, internal_ids)

    def remove(self, chunk_ids: list[str]) -> int:
        """Remove the given chunk ids from the in-memory index."""

        if not chunk_ids or self._index is None or self.size == 0:
            return 0

        target_ids = set(chunk_ids)
        internal_ids = np.asarray(
            [internal_id for internal_id, chunk_id in self._id_map.items() if chunk_id in target_ids],
            dtype=np.int64,
        )
        if internal_ids.size == 0:
            return 0

        removed = int(self._index.remove_ids(internal_ids))
        if removed > 0:
            for internal_id in internal_ids.tolist():
                self._id_map.pop(int(internal_id), None)
        return removed

    def search(
        self,
        query_vector: list[float] | np.ndarray,
        *,
        top_k: int = 10,
    ) -> list[VectorSearchHit]:
        """Search the index and return stable empty results for empty indexes."""

        if top_k <= 0:
            return []
        if self._index is None or self.size == 0:
            return []

        query = self._as_query(query_vector)
        distances, ids = self._index.search(query, top_k)

        hits: list[VectorSearchHit] = []
        for score, internal_id in zip(distances[0].tolist(), ids[0].tolist(), strict=True):
            if internal_id == -1:
                continue
            chunk_id = self._id_map.get(int(internal_id))
            if chunk_id is None:
                continue
            hits.append(VectorSearchHit(chunk_id=chunk_id, score=float(score)))
        return hits

    def save(self) -> None:
        """Persist the current index and metadata to disk."""

        if self._index is None or self._dimension is None:
            raise RuntimeError("Cannot save FAISS index before it is created or loaded.")

        self._faiss.write_index(self._index, str(self.index_path))
        metadata = {
            "dimension": self._dimension,
            "metric": self._metric,
            "next_internal_id": self._next_internal_id,
            "id_map": {str(key): value for key, value in self._id_map.items()},
        }
        self.metadata_path.write_text(json.dumps(metadata, indent=2, sort_keys=True), encoding="utf-8")

    def load(self) -> bool:
        """Load an existing persisted index. Returns False when no index exists yet."""

        if not self.index_path.exists() or not self.metadata_path.exists():
            self._index = None
            self._dimension = None
            self._metric = "cosine"
            self._id_map = {}
            self._next_internal_id = 0
            return False

        metadata = json.loads(self.metadata_path.read_text(encoding="utf-8"))
        self._index = self._faiss.read_index(str(self.index_path))
        self._dimension = int(metadata["dimension"])
        self._metric = metadata["metric"]
        self._next_internal_id = int(metadata["next_internal_id"])
        self._id_map = {int(key): value for key, value in metadata["id_map"].items()}
        return True

    def _ensure_index(self, dimension: int) -> None:
        if self._index is None:
            self.create(dimension, metric=self._metric)
            return
        if self._dimension != dimension:
            raise ValueError(
                f"Vector dimension mismatch: expected {self._dimension}, received {dimension}."
            )

    def _new_index(self, dimension: int, metric: MetricType):
        if metric == "cosine":
            return self._faiss.IndexIDMap2(self._faiss.IndexFlatIP(dimension))
        if metric == "l2":
            return self._faiss.IndexIDMap2(self._faiss.IndexFlatL2(dimension))
        raise ValueError(f"Unsupported FAISS metric: {metric}")

    def _prepare_vectors(self, matrix: np.ndarray) -> np.ndarray:
        prepared = matrix.copy()
        if self._metric == "cosine":
            self._faiss.normalize_L2(prepared)
        return prepared

    def _as_matrix(self, vectors: list[list[float]] | np.ndarray) -> np.ndarray:
        matrix = np.asarray(vectors, dtype=np.float32)
        if matrix.ndim != 2 or matrix.shape[0] == 0 or matrix.shape[1] == 0:
            raise ValueError("Vectors must be a non-empty 2D matrix.")
        return matrix

    def _as_query(self, query_vector: list[float] | np.ndarray) -> np.ndarray:
        query = np.asarray(query_vector, dtype=np.float32)
        if query.ndim != 1 or query.shape[0] == 0:
            raise ValueError("Query vector must be a non-empty 1D array.")
        self._ensure_index(query.shape[0])
        prepared = query.reshape(1, -1).copy()
        if self._metric == "cosine":
            self._faiss.normalize_L2(prepared)
        return prepared


def _load_faiss():
    try:
        import faiss
    except ImportError as exc:  # pragma: no cover - depends on runtime environment
        raise RuntimeError(
            "faiss-cpu is required to use the FAISS storage layer."
        ) from exc
    return faiss
