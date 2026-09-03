"""Evidence-gated async client for Geely Auto.

Network access happens only when a verified :class:`RequestSigner` is
supplied. Without it every operation raises ``GeelyProtocolUnavailable``
before touching the caller-owned session.

Transport outcomes map to the exception hierarchy so the coordinator can
react precisely:

- HTTP 401/403 -> :class:`GeelyAuthError` (token rotation required)
- HTTP 429     -> :class:`GeelyRateLimitError`
- other non-2xx -> :class:`GeelyProtocolError`
- transport/timeout failures -> :class:`GeelyConnectionError`
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any, NoReturn

from custom_components.geely_auto.api.endpoints import (
    VEHICLE_CAPABILITY,
    VEHICLE_LIST,
    VEHICLE_STATUS_LATEST,
)
from custom_components.geely_auto.api.exceptions import (
    GeelyAuthError,
    GeelyConnectionError,
    GeelyProtocolError,
    GeelyProtocolUnavailable,
    GeelyRateLimitError,
)
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

_AUTH_STATUS = frozenset({401, 403})
_RATE_LIMIT_STATUS = frozenset({429})
_HTTP_OK_MIN = 200
_HTTP_OK_MAX = 300
_MAX_ATTEMPTS = 3
_RETRY_BACKOFF_SECONDS = 0.5
_TRANSPORT_ERRORS = (TimeoutError, ConnectionError, OSError)


class GeelyAutoApi:
    """Define the stable API surface over the evidence-gated protocol layer."""

    def __init__(
        self,
        session: object,
        signer: RequestSigner | None = None,
        context: TspRequestContext | None = None,
        max_attempts: int = _MAX_ATTEMPTS,
        backoff_seconds: float = _RETRY_BACKOFF_SECONDS,
    ) -> None:
        """Keep a caller-owned session and an optional verified signer."""
        self._session = session
        self._signer: RequestSigner = (
            signer if signer is not None else UnverifiedSigner()
        )
        self._context = context
        self._max_attempts = max(1, max_attempts)
        self._backoff_seconds = backoff_seconds

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
        payload = await self._request_json(request)
        return parse_vehicle_list(payload)

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

    async def _request_json(self, request: GeelyApiRequest) -> Any:
        """Send the request with retry/rate-limit mapping, return JSON body."""
        last_error: GeelyConnectionError | GeelyProtocolError | None = None
        for attempt in range(1, self._max_attempts + 1):
            try:
                status, payload = await self._session_request(request)
            except _TRANSPORT_ERRORS as error:
                last_error = GeelyConnectionError(
                    f"transport failure talking to {request.url}: "
                    f"{type(error).__name__}: {error}"
                )
            else:
                if status in _AUTH_STATUS:
                    raise GeelyAuthError(
                        f"authentication rejected with HTTP {status}; "
                        "token rotation required"
                    )
                if status in _RATE_LIMIT_STATUS:
                    raise GeelyRateLimitError(
                        f"rate limited with HTTP {status} after {attempt} attempt(s)"
                    )
                if _HTTP_OK_MIN <= status < _HTTP_OK_MAX:
                    return payload
                last_error = GeelyProtocolError(
                    f"unexpected HTTP {status} from {request.url}"
                )
            if attempt < self._max_attempts:
                await asyncio.sleep(self._backoff_seconds * attempt)
        assert last_error is not None  # noqa: S101 - loop guarantees an error
        raise last_error

    async def _session_request(self, request: GeelyApiRequest) -> tuple[int, Any]:
        """Perform one request through the caller-owned aiohttp session."""
        response = await self._session.request(  # type: ignore[attr-defined]
            request.method,
            request.url,
            headers=request.headers,
            data=request.body,
        )
        return response.status, await response.json()


__all__ = ["GeelyAutoApi"]
