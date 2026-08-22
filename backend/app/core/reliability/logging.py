"""
TourSafe Structured JSON Logging & Sensitive Data Redaction.
Ensures all logs include trace_id, correlation_id, timestamp, and are sanitized against PII/secrets.
"""

import json
import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict
from .tracing import get_current_trace_id, get_current_correlation_id

SENSITIVE_KEYS = {
    "password", "token", "access_token", "refresh_token", "secret",
    "authorization", "api_key", "apikey", "pin", "kyc_document",
    "passport_number", "national_id", "ssn", "credit_card", "private_key"
}

JWT_PATTERN = re.compile(r"eyJ[a-zA-Z0-9_-]{10,}\.[a-zA-Z0-9_-]{10,}\.[a-zA-Z0-9_-]{10,}")
AUTH_HEADER_PATTERN = re.compile(r"(Bearer\s+)[A-Za-z0-9\-\._~\+\/]+=*", re.IGNORECASE)


def redact_sensitive_data(data: Any) -> Any:
    """Recursively scrub sensitive keys and regex patterns from dictionaries, lists, and strings."""
    if isinstance(data, dict):
        cleaned = {}
        for k, v in data.items():
            if str(k).lower() in SENSITIVE_KEYS:
                cleaned[k] = "[REDACTED_SECRET]"
            else:
                cleaned[k] = redact_sensitive_data(v)
        return cleaned
    elif isinstance(data, list):
        return [redact_sensitive_data(item) for item in data]
    elif isinstance(data, str):
        # Redact JWTs and Auth Bearer patterns
        scrubbed = JWT_PATTERN.sub("[REDACTED_JWT]", data)
        scrubbed = AUTH_HEADER_PATTERN.sub(r"\1[REDACTED_TOKEN]", scrubbed)
        return scrubbed
    return data


class StructuredJsonFormatter(logging.Formatter):
    """Formats log records as JSON lines with embedded tracing context."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "service": "toursafe-backend",
            "message": record.getMessage(),
            "trace_id": get_current_trace_id(),
            "correlation_id": get_current_correlation_id(),
        }

        if hasattr(record, "event"):
            log_entry["event"] = record.event

        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)

        # Merge additional custom fields if passed
        if hasattr(record, "extra_data") and isinstance(record.extra_data, dict):
            log_entry["data"] = redact_sensitive_data(record.extra_data)

        return json.dumps(redact_sensitive_data(log_entry))


def get_structured_logger(name: str = "toursafe") -> logging.Logger:
    """Get or configure a structured logger."""
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(StructuredJsonFormatter())
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger
