"""Tests for recursive and logging redaction."""

import logging

from custom_components.geely_auto.redaction import (
    REDACTED,
    RedactingLogFilter,
    redact_data,
    redact_text,
)


def test_recursive_redaction_covers_sensitive_fields() -> None:
    source = {
        "access_token": "example-access-value",
        "vehicle": {
            "vin": "VIN-WILL-BE-REMOVED",
            "latitude": 31.123456,
            "longitude": 121.123456,
            "safe": "kept",
        },
        "items": [{"device_id": "example-device-value"}],
    }

    sanitized = redact_data(source)

    assert sanitized["access_token"] == REDACTED
    assert sanitized["vehicle"]["vin"] == REDACTED
    assert sanitized["vehicle"]["latitude"] == REDACTED
    assert sanitized["vehicle"]["longitude"] == REDACTED
    assert sanitized["vehicle"]["safe"] == "kept"
    assert sanitized["items"][0]["device_id"] == REDACTED


def test_text_redaction_handles_phone_vin_token_and_coordinates() -> None:
    phone = "138" + "0" * 8
    vin = "L12345678" + "9ABCDEFG"
    text = (
        f"phone={phone} vin={vin} authorization=Bearer ExampleBearerValue; "
        "latitude=31.123 longitude=121.456"
    )

    sanitized = redact_text(text)

    assert phone not in sanitized
    assert vin not in sanitized
    assert "ExampleBearerValue" not in sanitized
    assert "31.123" not in sanitized
    assert "121.456" not in sanitized


def test_log_filter_removes_rendered_secret() -> None:
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="authorization=%s",
        args=("Bearer ExampleBearerValue",),
        exc_info=None,
    )

    assert RedactingLogFilter().filter(record) is True
    assert "ExampleBearerValue" not in record.getMessage()
    assert REDACTED in record.getMessage()
