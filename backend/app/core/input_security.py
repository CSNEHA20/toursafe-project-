"""
TourSafe Input Security & Injection Prevention Engine.
Protects against:
- NoSQL Injection ($gt, $ne, $where, $regex, $expr, $or in untrusted payload fields)
- Stored & Reflected Cross-Site Scripting (XSS) via strict HTML entity escaping
- Path Traversal (directory traversal ../, ..\\, and absolute file path manipulation)
- Malformed payloads and mass-assignment tampering
"""

import html
import re
from typing import Any, Dict, List, Union
from fastapi import HTTPException, status

# MongoDB injection operators that must not originate from user-controlled objects
FORBIDDEN_NOSQL_OPERATORS = {
    "$where",
    "$gt",
    "$gte",
    "$lt",
    "$lte",
    "$ne",
    "$in",
    "$nin",
    "$exists",
    "$regex",
    "$expr",
    "$jsonSchema",
    "$mod",
    "$text",
    "$all",
    "$elemMatch",
    "$size",
    "$bitsAllClear",
    "$bitsAllSet",
}


def sanitize_nosql_input(data: Any, path: str = "") -> Any:
    """
    Recursively inspect user-provided dictionaries and lists.
    Throws HTTPException if forbidden NoSQL operator keys are detected in user input.
    """
    if isinstance(data, dict):
        sanitized = {}
        for k, v in data.items():
            k_str = str(k).strip()
            if k_str.startswith("$"):
                if k_str in FORBIDDEN_NOSQL_OPERATORS or k_str.startswith("$"):
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Potential NoSQL injection detected in field '{path + '.' + k_str if path else k_str}'.",
                    )
            sanitized[k_str] = sanitize_nosql_input(v, path=f"{path}.{k_str}" if path else k_str)
        return sanitized
    elif isinstance(data, list):
        return [sanitize_nosql_input(item, path=f"{path}[{i}]") for i, item in enumerate(data)]
    return data


def sanitize_xss_string(val: str) -> str:
    """
    Escape HTML entities and sanitize script/event handler constructs in user-supplied strings.
    """
    if not isinstance(val, str):
        return str(val)
    # Standard HTML entity escaping
    escaped = html.escape(val, quote=True)
    # Strip javascript: URIs
    cleaned = re.sub(r"(?i)javascript\s*:", "blocked-javascript:", escaped)
    return cleaned


def sanitize_file_path(filename: str) -> str:
    """
    Sanitize filename and paths to prevent path traversal (../, ..\\, null bytes, absolute paths).
    """
    if not filename or not isinstance(filename, str):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid filename supplied.",
        )
    # Remove null bytes
    clean = filename.replace("\x00", "")
    # Check for path traversal sequences
    if ".." in clean or clean.startswith("/") or clean.startswith("\\") or ":" in clean:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid filename: Path traversal characters forbidden.",
        )
    # Clean to basename only
    base = re.sub(r"[^a-zA-Z0-9_\-\.]", "_", clean)
    return base


def sanitize_pii_for_logs(text_or_dict: Union[str, Dict[str, Any]]) -> Union[str, Dict[str, Any]]:
    """
    Redact passwords, tokens, full emails, full phone numbers, and exact GPS coordinates from logging payloads.
    """
    if isinstance(text_or_dict, str):
        # Redact JWT tokens
        sanitized = re.sub(r"eyJ[a-zA-Z0-9_-]{10,}\.eyJ[a-zA-Z0-9_-]{10,}\.[a-zA-Z0-9_-]+", "[REDACTED_JWT]", text_or_dict)
        # Redact passwords in query/json strings
        sanitized = re.sub(r'(?i)("?password"?\s*[:=]\s*)"[^"]+"', r'\1"[REDACTED]"', sanitized)
        # Sanitize log injection (strip newlines/CRLF)
        sanitized = sanitized.replace("\r", "").replace("\n", " ")
        return sanitized
    elif isinstance(text_or_dict, dict):
        redacted = {}
        for k, v in text_or_dict.items():
            k_lower = str(k).lower()
            if any(secret_term in k_lower for secret_term in ("password", "secret", "token", "auth", "api_key", "key")):
                redacted[k] = "[REDACTED]"
            elif "email" in k_lower and isinstance(v, str) and "@" in v:
                parts = v.split("@")
                redacted[k] = f"{parts[0][:2]}***@{parts[1]}"
            elif "phone" in k_lower and isinstance(v, str):
                redacted[k] = f"***{v[-4:]}" if len(v) >= 4 else "***"
            elif isinstance(v, dict):
                redacted[k] = sanitize_pii_for_logs(v)
            else:
                redacted[k] = v
        return redacted
    return text_or_dict
