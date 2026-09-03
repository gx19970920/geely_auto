"""Recursive and text redaction helpers for logs and protocol fixtures."""

from __future__ import annotations

import logging
import re
from collections.abc import Mapping, Sequence
from typing import Any, Final

REDACTED: Final = "<redacted>"

_SENSITIVE_KEYS = frozenset(
    {
        "access_token",
        "authorization",
        "cookie",
        "device_id",
        "deviceid",
        "devicesn",
        "device-sn",
        "x-device-id",
        "id_token",
        "latitude",
        "longitude",
        "mobile",
        "msisdn",
        "password",
        "phone",
        "plate",
        "platerno",
        "engineno",
        "pno18",
        "refresh_token",
        "request_id",
        "token",
        "txcookie",
        "usersig",
        "vin",
        "x-vehicle-identifier",
    }
)

_DIRECT_TEXT_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)"),
    re.compile(r"(?<![A-Z0-9])[A-HJ-NPR-Z0-9]{17}(?![A-Z0-9])", re.IGNORECASE),
)

_KEYED_TEXT_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(
        r"(?i)(authorization|cookie|access[_-]?token|refresh[_-]?token|"
        r"password|device[_-]?id|request[_-]?id)\s*([:=])\s*([^\r\n,;&]+)"
    ),
    re.compile(
        r"(?i)(latitude|longitude|lat|lon|lng)\s*([:=])\s*"
        r"[-+]?\d{1,3}(?:\.\d+)?"
    ),
)


def redact_text(value: str) -> str:
    """Redact common secret and privacy-bearing values from arbitrary text."""
    redacted = value
    for pattern in _DIRECT_TEXT_PATTERNS:
        redacted = pattern.sub(REDACTED, redacted)
    for pattern in _KEYED_TEXT_PATTERNS:
        redacted = pattern.sub(rf"\1\2{REDACTED}", redacted)
    return redacted


def redact_data(value: Any, *, key: str | None = None) -> Any:
    """Recursively redact structured capture or diagnostic data."""
    if key is not None and key.casefold() in _SENSITIVE_KEYS:
        return REDACTED
    if isinstance(value, Mapping):
        return {
            str(item_key): redact_data(item_value, key=str(item_key))
            for item_key, item_value in value.items()
        }
    if isinstance(value, str):
        return redact_text(value)
    if isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray)):
        return [redact_data(item) for item in value]
    return value


class RedactingLogFilter(logging.Filter):
    """Redact the rendered log message before handlers emit it."""

    def filter(self, record: logging.LogRecord) -> bool:
        """Replace message and arguments with a sanitized rendered string."""
        record.msg = redact_text(record.getMessage())
        record.args = ()
        return True
