"""Tests for the TSP request builder and the closed signing gate."""

import pytest

from custom_components.geely_auto.api import (
    VEHICLE_LIST,
    GeelyApiRequest,
    GeelyProtocolUnavailable,
    TspRequestContext,
    UnverifiedSigner,
    VehicleHeaderContext,
    build_tsp_request,
)


class FixedSigner:
    """Deterministic signer used to verify header assembly offline."""

    def __init__(self) -> None:
        self.seen: list[GeelyApiRequest] = []

    def signature(self, request: GeelyApiRequest) -> str:
        self.seen.append(request)
        return "fixed-signature"


CONTEXT = TspRequestContext(
    device_id="00000000-0000-0000-0000-000000000000",  # nosec-secret-scan (synthetic)
    app_version="3.54.0",
    device_brand="vivo",
    device_model="V2241A",
    device_os_version="Android 15 (API 35)",
)


def test_build_tsp_request_assembles_verified_header_set() -> None:
    signer = FixedSigner()

    request = build_tsp_request(
        VEHICLE_LIST,
        "test-access-token",
        CONTEXT,
        signer,
        VehicleHeaderContext(
            vehicle_identifier="<encoded-identifier>",
            vehicle_series="<encoded-series>",
            vehicle_brand="GEELY",
        ),
        nonce="00000000-1111-2222-3333-444444444444",
        timestamp_ms=1788427321230,
    )

    assert request.method == "GET"
    assert request.url == (
        "https://gric-api.geely.com"
        "/ms-vehicle-core/api/v1.0/vehicle/favorite-vehicles"
    )
    assert request.headers["X-TENANT-ID"] == "GEELY"
    assert request.headers["X-APP-ID"] == "GEELYCNCH001M0001"  # nosec-secret-scan (static app id)
    assert request.headers["X-API-SIGNATURE-VERSION"] == "2.1"
    assert request.headers["X-API-SIGNATURE-NONCE"] == (
        "00000000-1111-2222-3333-444444444444"
    )
    assert request.headers["X-TIMESTAMP"] == "1788427321230"
    assert request.headers["X-DEVICE-ID"] == CONTEXT.device_id
    assert request.headers["X-TSP-PLATFORM"] == "2"
    assert request.headers["X-VEHICLE-IDENTIFIER"] == "<encoded-identifier>"
    assert request.headers["X-VEHICLE-SERIES"] == "<encoded-series>"
    assert request.headers["X-SIGNATURE"] == "fixed-signature"
    assert "Content-Type" not in request.headers


def test_unverified_signer_keeps_gate_closed() -> None:
    request = GeelyApiRequest(
        method="GET",
        url="https://gric-api.geely.com/ms-vehicle-core/api/v1.0/vehicle/favorite-vehicles",
        headers={},
    )

    with pytest.raises(GeelyProtocolUnavailable, match="X-SIGNATURE"):
        UnverifiedSigner().signature(request)


def test_signer_receives_unsigned_request() -> None:
    signer = FixedSigner()

    build_tsp_request(
        VEHICLE_LIST,
        "test-access-token",
        CONTEXT,
        signer,
        nonce="n",
        timestamp_ms=1,
    )

    assert signer.seen[0].headers.get("X-SIGNATURE") is None
