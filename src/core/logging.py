"""JSON logs to stdout.

In a container the app writes to stdout and the platform collects it; one JSON object per line
can be filtered without parsing free text. Only the message and the fields passed explicitly
(`extra={...}`) are written. Emails are masked as a last line of defense: logs must carry no PII.
"""

import json
import logging
import re
import sys
from typing import Any

from src.core import clock

_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
# Attributes every LogRecord has; anything else came from `extra=` and is ours to print.
_STANDARD_ATTRS = set(logging.makeLogRecord({}).__dict__) | {"message", "asctime"}


def _redact(value: Any) -> Any:
    return _EMAIL.sub("[email]", value) if isinstance(value, str) else value


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": clock.now().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": _redact(record.getMessage()),
        }
        for key, value in record.__dict__.items():
            if key not in _STANDARD_ATTRS:
                payload[key] = _redact(value)
        if record.exc_info:
            # Full detail stays server-side; the host only ever sees a masked error.
            payload["exception"] = _redact(self.formatException(record.exc_info))
        return json.dumps(payload, default=str)


def configure_logging(level: str = "INFO") -> None:
    """Send every log of the process to stdout as JSON (replaces existing handlers)."""
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)
