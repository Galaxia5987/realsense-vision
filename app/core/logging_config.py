"""
Structured logging configuration for the RealSense Vision system.
Provides detailed, consistent logging across all components.
"""

import logging
import sys
from datetime import datetime
from typing import Optional
import json


class StructuredFormatter(logging.Formatter):
    """Pretty structured log formatter without colors."""

    def format(self, record):
        timestamp = datetime.now().strftime("%H:%M:%S")

        # Base log structure
        log_data = {
            "timestamp": timestamp,
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Custom fields
        if hasattr(record, "operation"):
            log_data["operation"] = getattr(record, "operation")

        # Exception if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        # JSON mode
        if getattr(record, "json_format", False):
            return json.dumps(log_data, ensure_ascii=False)

        # Pretty human-readable mode
        msg = f"[{log_data['timestamp']}] {log_data['level']:8s} [{log_data['logger']}] {log_data['message']}"

        # Extra structured block
        structured_parts = []
        for key in ("component", "operation", "status"):
            if key in log_data:
                structured_parts.append(f"{key}={log_data[key]}")
        if structured_parts:
            msg += " [" + ", ".join(structured_parts) + "]"

        # Exception block
        if "exception" in log_data:
            exc = "\n".join(
                "    " + line for line in log_data["exception"].splitlines()
            )
            msg += f"\n{exc}"

        return msg


class ComponentLogger:
    """Logger wrapper that adds component context to all log messages."""

    def __init__(self, component_name: str):
        self.component_name = component_name
        self.logger = logging.getLogger(component_name)

    def _log(
        self, level, message, operation=None, status=None, exc_info=False, **kwargs
    ):
        extra = {
            "component": self.component_name,
            "operation": operation,
            "status": status,
        }
        extra.update(kwargs)
        self.logger.log(level, message, extra=extra, exc_info=exc_info)

    def debug(self, message, operation=None, **kwargs):
        self._log(logging.DEBUG, message, operation=operation, **kwargs)

    def info(self, message, operation=None, status="info", **kwargs):
        self._log(logging.INFO, message, operation=operation, status=status, **kwargs)

    def warning(self, message, operation=None, status="warning", **kwargs):
        self._log(
            logging.WARNING, message, operation=operation, status=status, **kwargs
        )

    def error(self, message, operation=None, status="error", **kwargs):
        self._log(logging.ERROR, message, operation=operation, status=status, **kwargs)

    def critical(self, message, operation=None, status="critical", **kwargs):
        self._log(
            logging.CRITICAL, message, operation=operation, status=status, **kwargs
        )

    def exception(self, message, operation=None, **kwargs):
        self._log(
            logging.ERROR,
            message,
            operation=operation,
            status="exception",
            exc_info=True,
            **kwargs,
        )


def setup_logging(level=logging.INFO, log_file: Optional[str] = None):
    """
    Configure structured logging for the entire application.

    Args:
        level: Logging level (default: INFO)
        log_file: Optional file path for logging output
    """
    # Create formatter
    formatter = StructuredFormatter()

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Remove existing handlers
    root_logger.handlers.clear()

    # Console handler (stdout)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # File handler (optional)
    if log_file:
        try:
            file_handler = logging.FileHandler(log_file)
            file_handler.setLevel(level)
            file_handler.setFormatter(formatter)
            root_logger.addHandler(file_handler)
        except Exception as e:
            root_logger.error(f"Failed to setup file logging to {log_file}: {e}")

    return root_logger


def get_logger(component_name: str) -> ComponentLogger:
    """
    Get a structured logger for a specific component.

    Args:
        component_name: Name of the component (e.g., 'camera', 'detector', 'network_tables')

    Returns:
        ComponentLogger instance for the component
    """
    return ComponentLogger(component_name)
