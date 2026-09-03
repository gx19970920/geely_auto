"""End-to-end test over a real local HTTP socket.

Everything is real except the X-SIGNATURE (a fixed test signer): request
assembly, HTTP transport, envelope validation and parsing run against a
local aiohttp server.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any, ClassVar

import pytest

aiohttp: Any = pytest.importorskip("aiohttp")

from aiohttp import ClientSession, web  # noqa: E402

from custom_components.geely_auto.api import (  # noqa: E402
    Endpoint,
    TspRequestContext,
    build_tsp_request,
    parse_vehicle_list,
)
from custom_components.geely_auto.diagnostics import async_get_diagnostics  # noqa: E402

FIXTURE = Path(__file__).parent / "fixtures" / "gric_favorite_vehicles.json"
CONTEXT = TspRequestContext(
    device_id="00000000-0000-0000-0000-000000000000",  # nosec-secret-scan (synthetic)
    app_version="3.54.0",
)


class AcceptingSigner:
    """Deterministic signer; the only stand-in in this test."""

    def signature(self, request: Any) -> str:
        return "e2e-signature"


def test_full_pipeline_over_real_socket() -> None:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    received_headers: dict[str, str] = {}

    async def handler(request: Any) -> Any:
        received_headers.update(
            {str(k).lower(): str(v) for k, v in request.headers.items()}
        )
        assert request.headers["X-TENANT-ID"] == "GEELY"
        assert request.headers["X-SIGNATURE"] == "e2e-signature"
        assert "favorite-vehicles" in request.path
        return web.json_response(payload)

    async def scenario() -> tuple[int, list[str]]:
        app = web.Application()
        app.router.add_get(
            "/ms-vehicle-core/api/v1.0/vehicle/favorite-vehicles", handler
        )
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "127.0.0.1", 0)
        await site.start()
        host, port = runner.addresses[0][0], runner.addresses[0][1]
        try:
            local_endpoint = Endpoint(
                base=f"http://{host}:{port}",
                path="/ms-vehicle-core/api/v1.0/vehicle/favorite-vehicles",
                method="GET",
                evidence="verified-capture",
            )
            request = build_tsp_request(
                local_endpoint, "test-access-token", CONTEXT, AcceptingSigner()
            )
            async with ClientSession() as session:
                response = await session.request(
                    request.method, request.url, headers=request.headers
                )
                assert response.status == 200
                body = await response.json()
        finally:
            await runner.cleanup()
        summaries = parse_vehicle_list(body)
        return response.status, [v.vin for v in summaries]

    status, vins = asyncio.run(scenario())

    assert status == 200
    assert vins == ["VIN00000000000001"]
    assert received_headers["x-app-id"] == "GEELYCNCH001M0001"  # nosec-secret-scan (static app id)
    assert received_headers["authorization"] == "test-access-token"


def test_diagnostics_redacts_everything_sensitive() -> None:
    """Diagnostics output must not contain raw tokens or VINs."""
    entry_data = {
        "access_token": "secret-token-value",
        "device_id": "dev-123",
    }

    class FakeCoordinator:
        last_update_success = True
        data = None

    class FakeEntry:
        entry_id = "entry-1"
        data = entry_data

    class FakeHass:
        data: ClassVar[dict[str, Any]] = {}

    hass = FakeHass()
    hass.data = {"geely_auto": {"entry-1": FakeCoordinator()}}

    payload = asyncio.run(async_get_diagnostics(hass, FakeEntry()))

    assert payload["entry"]["data"]["access_token"] == "<redacted>"  # noqa: S105 - asserting redaction
    assert payload["entry"]["data"]["device_id"] == "<redacted>"
    assert "secret-token-value" not in json.dumps(payload)
