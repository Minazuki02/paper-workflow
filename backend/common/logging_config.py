"""Structured logging helpers for backend services."""

from __future__ import annotations

import json
import logging
import sys

try:
    import structlog
except ImportError:  # pragma: no cover - depends on runtime environment
    structlog = None

from backend.common.config import AppConfig, load_settings

_LOGGING_CONFIGURED = False


class _FallbackLogger:
    """Small stdlib-backed logger that mimics the subset of structlog we use."""

    def __init__(self, logger: logging.Logger, *, bindings: dict[str, object] | None = None) -> None:
        self._logger = logger
        self._bindings = bindings or {}

    def bind(self, **bindings: object) -> _FallbackLogger:
        return _FallbackLogger(self._logger, bindings={**self._bindings, **bindings})

    def debug(self, event_name: str, **kwargs: object) -> None:
        self._emit(logging.DEBUG, event_name, **kwargs)

    def info(self, event_name: str, **kwargs: object) -> None:
        self._emit(logging.INFO, event_name, **kwargs)

    def warning(self, event_name: str, **kwargs: object) -> None:
        self._emit(logging.WARNING, event_name, **kwargs)

    def error(self, event_name: str, **kwargs: object) -> None:
        self._emit(logging.ERROR, event_name, **kwargs)

    def _emit(self, level: int, event_name: str, **kwargs: object) -> None:
        payload = {"event_name": event_name, **self._bindings, **kwargs}
        self._logger.log(level, json.dumps(payload, sort_keys=True, default=str))


def configure_logging(
    settings: AppConfig | None = None,
    *,
    force: bool = False,
) -> None:
    """Configure a reusable JSON logger for backend modules."""

    global _LOGGING_CONFIGURED

    if _LOGGING_CONFIGURED and not force:
        return

    config = settings or load_settings()
    level_name = config.logging.level.upper()
    level = getattr(logging, level_name, logging.INFO)

    logging.basicConfig(
        level=level,
        format="%(message)s",
        stream=sys.stdout,
        force=True,
    )

    if structlog is None:
        _LOGGING_CONFIGURED = True
        return

    renderer: structlog.typing.Processor
    if config.logging.json_output:
        renderer = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer()

    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            renderer,
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    _LOGGING_CONFIGURED = True


def get_logger(name: str | None = None, **bindings: object):
    """Return a backend logger with optional persistent bindings."""

    if structlog is None:
        logger = _FallbackLogger(logging.getLogger(name or "paper-workflow-backend"))
        if bindings:
            logger = logger.bind(**bindings)
        return logger

    logger = structlog.get_logger(name or "paper-workflow-backend")
    if bindings:
        logger = logger.bind(**bindings)
    return logger
