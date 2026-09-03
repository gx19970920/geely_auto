"""Tests for the public exception hierarchy."""

import pytest

from custom_components.geely_auto.api import (
    GeelyAuthError,
    GeelyCommandError,
    GeelyConnectionError,
    GeelyError,
    GeelyProtocolError,
    GeelyProtocolUnavailable,
    GeelyRateLimitError,
)


@pytest.mark.parametrize(
    "error_type",
    [
        GeelyAuthError,
        GeelyCommandError,
        GeelyConnectionError,
        GeelyProtocolError,
        GeelyProtocolUnavailable,
        GeelyRateLimitError,
    ],
)
def test_public_errors_share_one_base(error_type) -> None:
    assert issubclass(error_type, GeelyError)


def test_protocol_unavailable_is_a_protocol_error() -> None:
    assert issubclass(GeelyProtocolUnavailable, GeelyProtocolError)
