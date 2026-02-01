"""Structured JSON logging for production observability.

Every log entry includes timestamp, level, module, and — when available —
the ``pipeline_run_id`` so that any log line can be traced back to the
exact pipeline execution that produced it.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime


class StructuredFormatter(logging.Formatter):
    """Emit each log record as a single JSON line."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry: dict[str, object] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
        }

        # Propagate custom context fields when present
        for attr in ("pipeline_run_id", "record_count", "source_name", "duration_seconds"):
            if hasattr(record, attr):
                log_entry[attr] = getattr(record, attr)

        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_entry, default=str)


def setup_logging(level: str = "INFO") -> None:
    """Configure root logger with structured JSON output."""
    handler = logging.StreamHandler()
    handler.setFormatter(StructuredFormatter())
    logging.root.handlers = [handler]
    logging.root.setLevel(getattr(logging, level.upper(), logging.INFO))


def get_logger(name: str) -> logging.Logger:
    """Return a named logger (call ``setup_logging`` first)."""
    return logging.getLogger(name)
