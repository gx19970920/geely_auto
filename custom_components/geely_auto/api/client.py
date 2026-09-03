"""Evidence-gated async client for Geely Auto.

Network access happens only when a verified :class:`RequestSigner` is
supplied. Without it every operation raises ``GeelyProtocolUnavailable``
before touching the caller-owned session.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, NoReturn

from custom_components.geely_auto.api.endpoints import (
    VEHICLE_CAPABILITY,
    VEHICLE_LIST,
    VEHICLE_STATUS_LATEST,
)
from custom_components.geely_auto.api.exceptions import GeelyProtocolUnavailable
from custom_components.geely_auto.api.parsers import (
    parse_vehicle_list,
)
from custom_components.geely_auto.api.signing import (
    GeelyApiRequest,
    TspRequestContext,
    UnverifiedSigner,
    VehicleHeaderContext,
    build_tsp_request,
    require_verified,
)

if TYPE_CHECKING:
    from custom_components.geely_auto.api.models import (
        TokenBundle,
        VehicleCapabilities,
        VehicleState,
        VehicleSummary,
    )
    from custom_components.geely_auto.api.signing import RequestSigner

_GATE_MESSAGE = (
    "No verified sanitized protocol capture is available; network access is disabled"
)


class GeelyAutoApi:
    """Define the stable API surface over the evidence-gated protocol layer."""

    def __init__(
        self,
        session: object,
        signer: RequestSigner | None = None,
        context: TspRequestContext | None = None,
    ) -> None:
        """Keep a caller-owned session and an optional verified signer."""
        self._session = session
        self._signer: RequestSigner = (
            signer if signer is not None else UnverifiedSigner()
        )
        self._context = context

    @staticmethod
    def _protocol_unavailable() -> NoReturn:
        raise GeelyProtocolUnavailable(_GATE_MESSAGE)

    async def refresh_token(self) -> TokenBundle:
        """Refresh authentication tokens once the token endpoint is verified."""
        self._protocol_unavailable()

    def build_vehicle_list_request(
        self,
        access_token: str,
        vehicle: VehicleHeaderContext | None = None,
    ) -> GeelyApiRequest:
        """Build the verified vehicle-list request (no network I/O)."""
        if self._context is None:
            raise GeelyProtocolUnavailable(
                "TspRequestContext is required to build TSP requests"
            )
        return build_tsp_request(
            VEHICLE_LIST,
            access_token,
            self._context,
            self._signer,
            vehicle,
        )

    async def get_vehicles(self, access_token: str) -> tuple[VehicleSummary, ...]:
        """Return all account vehicles via the verified list endpoint."""
        request = self.build_vehicle_list_request(access_token)
        response = await self._session_request(request)
        return parse_vehicle_list(response)

    async def get_vehicle_capabilities(self, vin: str) -> VehicleCapabilities:
        """Return normalized capabilities after the endpoint is verified."""
        del vin
        require_verified(VEHICLE_CAPABILITY)
        self._protocol_unavailable()

    async def get_vehicle_status(self, vin: str) -> VehicleState:
        """Return normalized vehicle state after the endpoint is verified."""
        del vin
        require_verified(VEHICLE_STATUS_LATEST)
        self._protocol_unavailable()

    async def _session_request(self, request: GeelyApiRequest) -> Any:
        """Perform the request through the caller-owned aiohttp session."""
        response = await self._session.request(  # type: ignore[attr-defined]
            request.method,
            request.url,
            headers=request.headers,
            data=request.body,
        )
        return await response.json()
