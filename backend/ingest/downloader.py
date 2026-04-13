"""PDF downloader for the Phase 1 fetch_pdf tool."""

from __future__ import annotations

import random
import time
from dataclasses import dataclass
from email.message import Message
from pathlib import Path
from typing import Protocol
from urllib import error as urllib_error
from urllib import parse, request as urllib_request

from backend.common.errors import (
    DOWNLOAD_INVALID_URL,
    DOWNLOAD_NOT_FOUND,
    DOWNLOAD_NOT_PDF,
    DOWNLOAD_RATE_LIMITED,
    DOWNLOAD_TIMEOUT,
    DOWNLOAD_TOO_LARGE,
)
from backend.storage.file_store import PdfFileStore

DEFAULT_TIMEOUT_SEC = 120.0
DEFAULT_MAX_SIZE_BYTES = 100 * 1024 * 1024
DEFAULT_CHUNK_SIZE = 64 * 1024


@dataclass(frozen=True)
class DownloadResult:
    """Canonical download result used by the fetch_pdf handler."""

    pdf_path: str
    file_size_bytes: int
    pdf_hash: str
    already_exists: bool


class DownloadError(Exception):
    """Structured downloader failure with a contract-aligned error code."""

    def __init__(self, error_code: str, message: str) -> None:
        super().__init__(message)
        self.error_code = error_code
        self.message = message


class ResponseLike(Protocol):
    """Small protocol used to support both urllib responses and test doubles."""

    headers: Message | dict[str, str]

    def read(self, size: int = -1) -> bytes: ...

    def __enter__(self) -> ResponseLike: ...

    def __exit__(self, exc_type, exc, tb) -> bool | None: ...


class PdfDownloader:
    """Download a PDF, validate it, and persist it through PdfFileStore."""

    def __init__(
        self,
        *,
        file_store: PdfFileStore | None = None,
        timeout_sec: float = DEFAULT_TIMEOUT_SEC,
        max_size_bytes: int = DEFAULT_MAX_SIZE_BYTES,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
        fetcher: callable | None = None,
        sleeper: callable | None = None,
        randomizer: callable | None = None,
    ) -> None:
        self._file_store = file_store or PdfFileStore()
        self._timeout_sec = timeout_sec
        self._max_size_bytes = max_size_bytes
        self._chunk_size = chunk_size
        self._fetcher = fetcher or self._default_fetcher
        self._sleeper = sleeper or time.sleep
        self._randomizer = randomizer or random.random

    def download(self, url: str, filename: str | None = None) -> DownloadResult:
        """Download a PDF from a URL and store it by hash."""

        _ = filename
        normalized_url = self._validate_url(url)

        attempt = 0
        while True:
            attempt += 1
            try:
                return self._download_once(normalized_url)
            except DownloadError as exc:
                if not self._should_retry(exc.error_code, attempt):
                    raise
                self._sleeper(self._compute_backoff_delay(exc.error_code, attempt))

    def _download_once(self, url: str) -> DownloadResult:
        try:
            with self._fetcher(url, self._timeout_sec) as response:
                content = self._read_pdf_bytes(response)
        except TimeoutError as exc:
            raise DownloadError(DOWNLOAD_TIMEOUT, "PDF download timed out") from exc
        except urllib_error.HTTPError as exc:
            if exc.code == 404:
                raise DownloadError(DOWNLOAD_NOT_FOUND, "PDF URL returned HTTP 404") from exc
            if exc.code in {403, 429}:
                raise DownloadError(
                    DOWNLOAD_RATE_LIMITED,
                    f"PDF download was rate limited with HTTP {exc.code}",
                ) from exc
            raise DownloadError(
                DOWNLOAD_INVALID_URL,
                f"PDF download failed with HTTP {exc.code}",
            ) from exc
        except urllib_error.URLError as exc:
            reason = getattr(exc, "reason", None)
            if isinstance(reason, TimeoutError):
                raise DownloadError(DOWNLOAD_TIMEOUT, "PDF download timed out") from exc
            raise DownloadError(DOWNLOAD_INVALID_URL, "PDF URL is unreachable") from exc

        pdf_path, pdf_hash, already_exists = self._file_store.save_bytes(content)
        return DownloadResult(
            pdf_path=pdf_path,
            file_size_bytes=len(content),
            pdf_hash=pdf_hash,
            already_exists=already_exists,
        )

    def _read_pdf_bytes(self, response: ResponseLike) -> bytes:
        content_length = self._parse_content_length(response.headers)
        if content_length is not None and content_length > self._max_size_bytes:
            raise DownloadError(DOWNLOAD_TOO_LARGE, "PDF exceeds the maximum size limit")

        chunks: list[bytes] = []
        total_bytes = 0
        while True:
            chunk = response.read(self._chunk_size)
            if not chunk:
                break
            total_bytes += len(chunk)
            if total_bytes > self._max_size_bytes:
                raise DownloadError(DOWNLOAD_TOO_LARGE, "PDF exceeds the maximum size limit")
            chunks.append(chunk)

        content = b"".join(chunks)
        if not self._is_pdf_content(response.headers, content):
            raise DownloadError(DOWNLOAD_NOT_PDF, "Downloaded content is not a PDF")
        return content

    def _validate_url(self, url: str) -> str:
        normalized = url.strip()
        parsed = parse.urlparse(normalized)
        if not normalized or parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise DownloadError(DOWNLOAD_INVALID_URL, "URL must be a valid http(s) address")
        return normalized

    def _should_retry(self, error_code: str, attempt: int) -> bool:
        limits = {
            DOWNLOAD_TIMEOUT: 3,
            DOWNLOAD_RATE_LIMITED: 5,
        }
        max_attempts = limits.get(error_code)
        return max_attempts is not None and attempt < max_attempts

    def _compute_backoff_delay(self, error_code: str, attempt: int) -> float:
        base_delay = {
            DOWNLOAD_TIMEOUT: 5.0,
            DOWNLOAD_RATE_LIMITED: 30.0,
        }[error_code]
        delay = min(base_delay * (2 ** (attempt - 1)), 300.0)
        jitter = 0.5 + self._randomizer()
        return delay * jitter

    def _default_fetcher(self, url: str, timeout_sec: float) -> ResponseLike:
        request = urllib_request.Request(
            url,
            headers={"User-Agent": "paper-workflow-backend/0.1"},
        )
        return urllib_request.urlopen(request, timeout=timeout_sec)

    def _parse_content_length(self, headers: Message | dict[str, str]) -> int | None:
        header_value = self._get_header(headers, "Content-Length")
        if not header_value:
            return None
        try:
            return int(header_value)
        except ValueError:
            return None

    def _is_pdf_content(self, headers: Message | dict[str, str], content: bytes) -> bool:
        content_type = (self._get_header(headers, "Content-Type") or "").lower()
        if "application/pdf" in content_type:
            return content.startswith(b"%PDF-")
        if "application/octet-stream" in content_type or not content_type:
            return content.startswith(b"%PDF-")
        return False

    def _get_header(self, headers: Message | dict[str, str], name: str) -> str | None:
        if isinstance(headers, Message):
            return headers.get(name)

        lowered_name = name.lower()
        for key, value in headers.items():
            if key.lower() == lowered_name:
                return value
        return None

