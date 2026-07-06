"""Recursive secret redaction for anything written to runs/ or transcripts.

Providers echo auth headers, key query params, and bearer tokens in request
metadata; the spec mandates recording raw_request/raw_response, so redaction is
mandatory, not optional.
"""

from __future__ import annotations

import re

PLACEHOLDER = "***REDACTED***"

_SENSITIVE_KEYS = {"authorization", "x-api-key", "api-key", "api_key", "key", "token", "secret"}

# Token-like patterns embedded in free strings / URLs.
_PATTERNS = [
    (re.compile(r"Bearer\s+[A-Za-z0-9._\-]+", re.IGNORECASE), PLACEHOLDER),
    (re.compile(r"sk-[A-Za-z0-9._\-]{8,}"), PLACEHOLDER),
    # Keep the "key=" prefix, redact only the value (capture group, no lookbehind).
    (
        re.compile(r"([?&](?:key|token|api_key|access_token)=)[^&\s]+", re.IGNORECASE),
        r"\1" + PLACEHOLDER,
    ),
]


def _redact_str(s: str) -> str:
    out = s
    for pat, repl in _PATTERNS:
        out = pat.sub(repl, out)
    return out


def redact(obj):
    """Return a deep-redacted copy of a dict/list/str; other types pass through."""
    if isinstance(obj, dict):
        result = {}
        for k, v in obj.items():
            if isinstance(k, str) and k.lower() in _SENSITIVE_KEYS:
                result[k] = PLACEHOLDER
            else:
                result[k] = redact(v)
        return result
    if isinstance(obj, (list, tuple)):
        return [redact(v) for v in obj]
    if isinstance(obj, str):
        return _redact_str(obj)
    return obj
