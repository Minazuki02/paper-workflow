"""PDF file storage helpers backed by the configured data directory."""

from __future__ import annotations

import hashlib
import shutil
from pathlib import Path

from backend.common.config import AppConfig, load_settings


class PdfFileStore:
    """Manage PDF persistence without coupling to ingest business logic."""

    def __init__(self, settings: AppConfig | None = None) -> None:
        self._settings = settings or load_settings()
        self._pdf_root = self._settings.paths.pdf_dir
        self._pdf_root.mkdir(parents=True, exist_ok=True)

    @property
    def pdf_root(self) -> Path:
        return self._pdf_root

    def save_bytes(self, content: bytes) -> tuple[str, str, bool]:
        """Persist PDF bytes and return `(relative_path, sha256, already_exists)`."""

        pdf_hash = hashlib.sha256(content).hexdigest()
        target = self._target_path(pdf_hash)
        already_exists = target.exists()

        if not already_exists:
            target.write_bytes(content)

        return self._relative_path(target), pdf_hash, already_exists

    def save_file(self, source_path: str | Path) -> tuple[str, str, bool]:
        """Persist a local PDF file and return `(relative_path, sha256, already_exists)`."""

        source = Path(source_path).expanduser().resolve()
        pdf_hash = self.compute_hash(source)
        target = self._target_path(pdf_hash)
        already_exists = target.exists()

        if not already_exists:
            shutil.copyfile(source, target)

        return self._relative_path(target), pdf_hash, already_exists

    def exists(self, pdf_hash: str) -> bool:
        """Return whether the PDF for the given hash is already stored."""

        return self._target_path(pdf_hash).exists()

    def get_relative_path(self, pdf_hash: str) -> str:
        """Return the relative storage path for a given PDF hash."""

        return self._relative_path(self._target_path(pdf_hash))

    def get_absolute_path(self, relative_path: str | Path) -> Path:
        """Resolve a stored relative path to an absolute path under the PDF root."""

        candidate = (self._pdf_root / relative_path).resolve()
        candidate.relative_to(self._pdf_root.resolve())
        return candidate

    @staticmethod
    def compute_hash(source_path: str | Path) -> str:
        """Compute the SHA-256 digest of a local file."""

        hasher = hashlib.sha256()
        with Path(source_path).expanduser().resolve().open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                hasher.update(chunk)
        return hasher.hexdigest()

    def _target_path(self, pdf_hash: str) -> Path:
        shard = pdf_hash[:2]
        directory = self._pdf_root / shard
        directory.mkdir(parents=True, exist_ok=True)
        return directory / f"{pdf_hash}.pdf"

    def _relative_path(self, absolute_path: Path) -> str:
        return str(absolute_path.relative_to(self._pdf_root))
