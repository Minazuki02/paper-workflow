"""Shared ToolError helpers and error code constants."""

from __future__ import annotations

from typing import Any

from backend.common.models import ToolError

SEARCH_RATE_LIMITED = "SEARCH_RATE_LIMITED"
SEARCH_API_ERROR = "SEARCH_API_ERROR"
SEARCH_TIMEOUT = "SEARCH_TIMEOUT"
SEARCH_INVALID_QUERY = "SEARCH_INVALID_QUERY"

DOWNLOAD_TIMEOUT = "DOWNLOAD_TIMEOUT"
DOWNLOAD_NOT_FOUND = "DOWNLOAD_NOT_FOUND"
DOWNLOAD_RATE_LIMITED = "DOWNLOAD_RATE_LIMITED"
DOWNLOAD_INVALID_URL = "DOWNLOAD_INVALID_URL"
DOWNLOAD_NOT_PDF = "DOWNLOAD_NOT_PDF"
DOWNLOAD_TOO_LARGE = "DOWNLOAD_TOO_LARGE"

INGEST_INVALID_URL = "INGEST_INVALID_URL"
INGEST_DEDUP_CONFLICT = "INGEST_DEDUP_CONFLICT"
INGEST_QUEUE_FULL = "INGEST_QUEUE_FULL"
INGEST_BATCH_TOO_LARGE = "INGEST_BATCH_TOO_LARGE"

PARSE_CORRUPT_PDF = "PARSE_CORRUPT_PDF"
PARSE_ENCRYPTED = "PARSE_ENCRYPTED"
PARSE_NO_TEXT = "PARSE_NO_TEXT"
PARSE_GROBID_UNAVAILABLE = "PARSE_GROBID_UNAVAILABLE"

EMBED_OOM = "EMBED_OOM"
EMBED_MODEL_UNAVAILABLE = "EMBED_MODEL_UNAVAILABLE"

INDEX_WRITE_FAILED = "INDEX_WRITE_FAILED"
DB_WRITE_FAILED = "DB_WRITE_FAILED"
DEDUP_CONFLICT = "DEDUP_CONFLICT"

RETRIEVE_EMPTY_INDEX = "RETRIEVE_EMPTY_INDEX"
RETRIEVE_INVALID_PAPER = "RETRIEVE_INVALID_PAPER"
RETRIEVE_QUERY_TOO_LONG = "RETRIEVE_QUERY_TOO_LONG"
RETRIEVE_MODEL_ERROR = "RETRIEVE_MODEL_ERROR"

ANALYZE_PAPER_NOT_FOUND = "ANALYZE_PAPER_NOT_FOUND"
ANALYZE_PAPER_NOT_READY = "ANALYZE_PAPER_NOT_READY"
ANALYZE_LLM_ERROR = "ANALYZE_LLM_ERROR"
ANALYZE_CONTEXT_TOO_LONG = "ANALYZE_CONTEXT_TOO_LONG"

COMPARE_TOO_FEW_PAPERS = "COMPARE_TOO_FEW_PAPERS"
COMPARE_TOO_MANY_PAPERS = "COMPARE_TOO_MANY_PAPERS"
COMPARE_PAPER_NOT_READY = "COMPARE_PAPER_NOT_READY"
COMPARE_LLM_ERROR = "COMPARE_LLM_ERROR"

SYNTH_TOPIC_TOO_BROAD = "SYNTH_TOPIC_TOO_BROAD"
SYNTH_NOT_ENOUGH_PAPERS = "SYNTH_NOT_ENOUGH_PAPERS"
SYNTH_LLM_ERROR = "SYNTH_LLM_ERROR"

STATUS_NOT_FOUND = "STATUS_NOT_FOUND"

REINDEX_PAPER_NOT_FOUND = "REINDEX_PAPER_NOT_FOUND"
REINDEX_PAPER_NOT_READY = "REINDEX_PAPER_NOT_READY"
REINDEX_MODEL_ERROR = "REINDEX_MODEL_ERROR"
REINDEX_IN_PROGRESS = "REINDEX_IN_PROGRESS"

SYSTEM_INTERNAL_ERROR = "SYSTEM_INTERNAL_ERROR"
SYSTEM_NOT_INITIALIZED = "SYSTEM_NOT_INITIALIZED"
SYSTEM_DISK_FULL = "SYSTEM_DISK_FULL"


ERROR_MESSAGES: dict[str, str] = {
    SEARCH_RATE_LIMITED: "搜索 API 限流，请稍后重试",
    SEARCH_API_ERROR: "搜索 API 返回错误",
    SEARCH_TIMEOUT: "搜索超时",
    SEARCH_INVALID_QUERY: "搜索词无效",
    DOWNLOAD_TIMEOUT: "下载超时（默认 120s）",
    DOWNLOAD_NOT_FOUND: "URL 返回 404",
    DOWNLOAD_RATE_LIMITED: "下载被限流",
    DOWNLOAD_INVALID_URL: "URL 格式无效",
    DOWNLOAD_NOT_PDF: "下载内容不是 PDF 格式",
    DOWNLOAD_TOO_LARGE: "PDF 超过大小限制（默认 100MB）",
    INGEST_INVALID_URL: "URL 格式无效或不可达",
    INGEST_DEDUP_CONFLICT: "论文已存在（返回已有 paper_id）",
    INGEST_QUEUE_FULL: "ingest 队列已满，请稍后",
    INGEST_BATCH_TOO_LARGE: "批量数超过上限（100）",
    PARSE_CORRUPT_PDF: "PDF 损坏或无法打开",
    PARSE_ENCRYPTED: "PDF 已加密",
    PARSE_NO_TEXT: "PDF 无可提取文本",
    PARSE_GROBID_UNAVAILABLE: "GROBID 服务不可用",
    EMBED_OOM: "embedding 模型内存不足",
    EMBED_MODEL_UNAVAILABLE: "embedding 模型不可用",
    INDEX_WRITE_FAILED: "向量索引写入失败",
    DB_WRITE_FAILED: "数据库写入失败",
    DEDUP_CONFLICT: "去重冲突",
    RETRIEVE_EMPTY_INDEX: "向量索引为空，请先 ingest 论文",
    RETRIEVE_INVALID_PAPER: "指定的 paper_id 不存在",
    RETRIEVE_QUERY_TOO_LONG: "query 超长（>2000 字符）",
    RETRIEVE_MODEL_ERROR: "embedding 模型错误",
    ANALYZE_PAPER_NOT_FOUND: "paper_id 不存在",
    ANALYZE_PAPER_NOT_READY: "论文尚未完成 ingest（status != ready）",
    ANALYZE_LLM_ERROR: "LLM 调用失败",
    ANALYZE_CONTEXT_TOO_LONG: "论文内容超出 LLM 上下文窗口",
    COMPARE_TOO_FEW_PAPERS: "至少需要 2 篇论文",
    COMPARE_TOO_MANY_PAPERS: "最多支持 10 篇论文",
    COMPARE_PAPER_NOT_READY: "部分论文尚未完成 ingest",
    COMPARE_LLM_ERROR: "LLM 调用失败",
    SYNTH_TOPIC_TOO_BROAD: "主题过于宽泛，建议缩窄",
    SYNTH_NOT_ENOUGH_PAPERS: "相关论文不足（<3 篇）",
    SYNTH_LLM_ERROR: "LLM 调用失败",
    STATUS_NOT_FOUND: "job_id 或 paper_id 不存在",
    REINDEX_PAPER_NOT_FOUND: "paper_id 不存在",
    REINDEX_PAPER_NOT_READY: "论文状态不是 ready/indexed",
    REINDEX_MODEL_ERROR: "指定的 embedding 模型不可用",
    REINDEX_IN_PROGRESS: "该论文正在被其他 reindex job 处理",
    SYSTEM_INTERNAL_ERROR: "内部错误",
    SYSTEM_NOT_INITIALIZED: "backend 未初始化",
    SYSTEM_DISK_FULL: "磁盘空间不足",
}

# Only codes with explicit retry guidance in 02, or clearly transient system conditions,
# get a default retryable=True mapping here. Callers can still override per case.
RETRYABLE_ERROR_CODES = frozenset(
    {
        SEARCH_RATE_LIMITED,
        SEARCH_API_ERROR,
        SEARCH_TIMEOUT,
        DOWNLOAD_TIMEOUT,
        DOWNLOAD_RATE_LIMITED,
        PARSE_GROBID_UNAVAILABLE,
        EMBED_OOM,
        EMBED_MODEL_UNAVAILABLE,
        INDEX_WRITE_FAILED,
        DB_WRITE_FAILED,
        RETRIEVE_MODEL_ERROR,
        ANALYZE_LLM_ERROR,
        REINDEX_MODEL_ERROR,
    }
)

NON_RETRYABLE_ERROR_CODES = frozenset(set(ERROR_MESSAGES) - set(RETRYABLE_ERROR_CODES))


def is_retryable_error(error_code: str) -> bool:
    """Return the default retryable flag for a known error code."""

    return error_code in RETRYABLE_ERROR_CODES


def build_tool_error(
    error_code: str,
    *,
    error_message: str | None = None,
    retryable: bool | None = None,
    details: dict[str, Any] | None = None,
) -> ToolError:
    """Construct the canonical ToolError payload used by every MCP tool."""

    if error_code not in ERROR_MESSAGES:
        raise ValueError(f"Unknown error code: {error_code}")

    return ToolError(
        error_code=error_code,
        error_message=error_message or ERROR_MESSAGES[error_code],
        retryable=is_retryable_error(error_code) if retryable is None else retryable,
        details=details,
    )


def system_internal_error(*, details: dict[str, Any] | None = None) -> ToolError:
    """Shortcut for the common internal-error response."""

    return build_tool_error(SYSTEM_INTERNAL_ERROR, details=details)

