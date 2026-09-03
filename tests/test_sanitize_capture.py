"""Tests for capture-copy sanitization."""

import json

from scripts.sanitize_capture import sanitize_content


def test_json_capture_preserves_shape_and_removes_values() -> None:
    source = json.dumps(
        {
            "request": {"headers": {"authorization": "ExampleBearerValue"}},
            "response": {"vin": "example-private-vin", "soc": 52.5},
        }
    )

    sanitized = json.loads(sanitize_content(source))

    assert sanitized["request"]["headers"]["authorization"] == "<redacted>"
    assert sanitized["response"]["vin"] == "<redacted>"
    assert sanitized["response"]["soc"] == 52.5


def test_plain_text_capture_is_sanitized() -> None:
    phone = "139" + "1" * 8

    sanitized = sanitize_content(f"mobile={phone}")

    assert phone not in sanitized
