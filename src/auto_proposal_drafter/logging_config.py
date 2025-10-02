from __future__ import annotations

import logging
import sys
from contextvars import ContextVar
from typing import Any

from google.cloud import logging as cloud_logging

# Context variable for trace ID
trace_id_var: ContextVar[str | None] = ContextVar("trace_id", default=None)


class StructuredFormatter(logging.Formatter):
    """JSON formatter for structured logging compatible with Cloud Logging."""

    def format(self, record: logging.LogRecord) -> str:
        import json
        from datetime import datetime

        log_obj = {
            "timestamp": datetime.utcfromtimestamp(record.created).isoformat() + "Z",
            "severity": record.levelname,
            "message": record.getMessage(),
            "logger": record.name,
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Add trace ID if available
        trace_id = trace_id_var.get()
        if trace_id:
            log_obj["logging.googleapis.com/trace"] = trace_id

        # Add extra fields
        if hasattr(record, "extra"):
            log_obj.update(record.extra)

        # Add exception info
        if record.exc_info:
            log_obj["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_obj)


def setup_logging(
    *,
    environment: str = "dev",
    project_id: str | None = None,
    use_cloud_logging: bool = True,
) -> None:
    """Configure logging for the application.

    Args:
        environment: Environment name (dev, staging, prod)
        project_id: GCP project ID for Cloud Logging
        use_cloud_logging: Whether to use Cloud Logging client
    """
    log_level = logging.DEBUG if environment == "dev" else logging.INFO

    if use_cloud_logging and project_id and environment != "dev":
        # Use Cloud Logging client
        client = cloud_logging.Client(project=project_id)
        client.setup_logging(log_level=log_level)
    else:
        # Use structured JSON logging to stdout
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(StructuredFormatter())

        logging.basicConfig(
            level=log_level,
            handlers=[handler],
        )

    # Set levels for noisy libraries
    logging.getLogger("google").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)


def set_trace_id(trace_id: str) -> None:
    """Set the trace ID for the current context."""
    trace_id_var.set(trace_id)


def get_trace_id() -> str | None:
    """Get the trace ID from the current context."""
    return trace_id_var.get()


__all__ = ["setup_logging", "set_trace_id", "get_trace_id", "StructuredFormatter"]
