"""Tests for transport mapping: 401, 429, retries, transport errors, parsing."""

import asyncio
import json
from collections.abc import Coroutine
from pathlib import Path
from typing import Any

import pytest

from custom_components.geely_auto.api import (
    GeelyAuthError,
    GeelyAutoApi,
    GeelyConnectionError,
    GeelyProtocolError,
    GeelyRateLimitError,
    TspRequestContext,
)


class OfflineSession:
    """Scripted responses without any real I/O."""

    def __init__(self, script: list[Any]) -> None:
        self._script = list(script)
        self.calls = 0

    async def request(self, method: str, url: str, **kwargs: Any) -> Any:
        self.calls += 1
        outcome = self._script.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        status, payload = outcome
        return CannedResponse(status, payload)


class CannedResponse:
    """Minimal status + async-json response stand-in."""

    def __init__(self, status: int, payload: dict[str, Any]) -> None:
        self.status = status
        self._payload = payload

    async def json(self) -> dict[str, Any]:
        return self._payload


class AcceptingSigner:
    """Signer stand-in for offline pipeline tests."""

    def signature(self, request: Any) -> str:
        return "offline-signature"


def build_api(session: OfflineSession) -> GeelyAutoApi:
    return GeelyAutoApi(
        session,
        signer=AcceptingSigner(),
        context=TspRequestContext(
            device_id="00000000-0000-0000-0000-000000000000",  # nosec-secret-scan (synthetic)
            app_version="3.54.0",
        ),
        backoff_seconds=0,
    )


def run(coroutine: Coroutine[Any, Any, Any]) -> Any:
    return asyncio.run(coroutine)


def fixture_payload() -> dict[str, Any]:
    fixture = Path(__file__).parent / "fixtures" / "gric_favorite_vehicles.json"
    return json.loads(fixture.read_text(encoding="utf-8"))


def test_http_401_maps_to_auth_error() -> None:
    api = build_api(OfflineSession([(401, {})]))

    with pytest.raises(GeelyAuthError, match="token rotation"):
        run(api.get_vehicles("test-access-token"))


def test_http_429_maps_to_rate_limit_error() -> None:
    api = build_api(OfflineSession([(429, {})]))

    with pytest.raises(GeelyRateLimitError, match="rate limited"):
        run(api.get_vehicles("test-access-token"))


def test_transport_failure_maps_to_connection_error() -> None:
    api = build_api(OfflineSession([ConnectionError("reset by peer")] * 3))

    with pytest.raises(GeelyConnectionError, match="transport failure"):
        run(api.get_vehicles("test-access-token"))


def test_unexpected_http_status_maps_to_protocol_error() -> None:
    api = build_api(OfflineSession([(500, {})] * 3))

    with pytest.raises(GeelyProtocolError, match="HTTP 500"):
        run(api.get_vehicles("test-access-token"))


def test_transport_failure_retries_then_recovers() -> None:
    session = OfflineSession(
        [
            ConnectionError("reset by peer"),
            (200, fixture_payload()),
        ]
    )
    api = build_api(session)

    summaries = run(api.get_vehicles("test-access-token"))

    assert len(summaries) == 1
    assert session.calls == 2


def test_transport_failure_gives_up_after_max_attempts() -> None:
    session = OfflineSession([ConnectionError("down")] * 5)
    api = build_api(session)

    with pytest.raises(GeelyConnectionError):
        run(api.get_vehicles("test-access-token"))

    assert session.calls == 3


def test_success_with_multi_vehicle_payload() -> None:
    payload = fixture_payload()
    payload["data"].append(dict(payload["data"][0], vin="VIN00000000000002"))
    session = OfflineSession([(200, payload)])
    api = build_api(session)

    summaries = run(api.get_vehicles("test-access-token"))

    assert [v.vin for v in summaries] == [
        "VIN00000000000001",
        "VIN00000000000002",
    ]
