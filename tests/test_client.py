"""Tests for the closed protocol gate and zero-network behavior."""

import asyncio
import json
from collections.abc import Coroutine
from pathlib import Path
from typing import Any

import pytest

from custom_components.geely_auto.api import (
    GeelyAutoApi,
    GeelyProtocolUnavailable,
    TspRequestContext,
    parse_vehicle_list,
)


class ExplodingSession:
    """Fail if any attribute is accessed as part of a network attempt."""

    def __getattr__(self, name: str) -> None:
        pytest.fail(f"Unexpected session access: {name}")


class OfflineSession:
    """Serve a canned JSON payload without any real I/O."""

    def __init__(self, payload: dict[str, Any]) -> None:
        self._payload = payload
        self.requests: list[tuple[str, str]] = []

    async def request(self, method: str, url: str, **kwargs: Any) -> Any:
        self.requests.append((method, url))
        return CannedResponse(self._payload)


class CannedResponse:
    """Minimal async-json response stand-in."""

    def __init__(self, payload: dict[str, Any]) -> None:
        self._payload = payload

    async def json(self) -> dict[str, Any]:
        return self._payload


class AcceptingSigner:
    """Signer stand-in for the offline pipeline test."""

    def signature(self, request: Any) -> str:
        return "offline-signature"


def run(coroutine: Coroutine[Any, Any, Any]) -> Any:
    return asyncio.run(coroutine)


@pytest.mark.parametrize(
    "operation",
    [
        lambda api: api.refresh_token(),
        lambda api: api.get_vehicles("TOKEN_NOT_USED"),
        lambda api: api.get_vehicle_capabilities("VIN_NOT_SENT"),
        lambda api: api.get_vehicle_status("VIN_NOT_SENT"),
    ],
)
def test_every_operation_stops_before_network(operation) -> None:
    api = GeelyAutoApi(ExplodingSession())

    # Each operation must stop on its own gate before any session access.
    with pytest.raises(GeelyProtocolUnavailable):
        run(operation(api))


def test_client_without_context_cannot_build_requests() -> None:
    api = GeelyAutoApi(ExplodingSession())

    with pytest.raises(GeelyProtocolUnavailable, match="TspRequestContext"):
        api.build_vehicle_list_request("test-access-token")


def test_offline_pipeline_parses_fixture_response() -> None:
    fixture = (
        Path(__file__).parent
        / "fixtures"
        / "gric_favorite_vehicles.json"
    )
    payload = json.loads(fixture.read_text(encoding="utf-8"))
    session = OfflineSession(payload)
    api = GeelyAutoApi(
        session,
        signer=AcceptingSigner(),
        context=TspRequestContext(
            device_id="00000000-0000-0000-0000-000000000000",  # nosec-secret-scan (synthetic)
            app_version="3.54.0",
        ),
    )

    summaries = run(api.get_vehicles("test-access-token"))

    assert len(summaries) == 1
    assert summaries[0].vin == "VIN00000000000001"
    assert session.requests[0][0] == "GET"
    assert "favorite-vehicles" in session.requests[0][1]


def test_parser_reexport_matches_module() -> None:
    assert GeelyAutoApi is not None
    assert callable(parse_vehicle_list)
