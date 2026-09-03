"""Request builder and signer interface for the verified TSP header set.

The header set below was observed verbatim in a sanitized capture of the
logged-in Geely app against ``gric-api.geely.com``. Every header is built
here except ``X-SIGNATURE``: its HMAC input string and key material are not
yet verified, so a :class:`RequestSigner` implementation must be supplied.
The default signer keeps the protocol gate closed.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Protocol

from custom_components.geely_auto.api.exceptions import GeelyProtocolUnavailable
from custom_components.geely_auto.const import (
    APP_ID,
    TENANT_ID,
    TSP_PLATFORM,
    X_API_SIGNATURE_VERSION,
)

if TYPE_CHECKING:
    from custom_components.geely_auto.api.endpoints import Endpoint

_GATE_MESSAGE = (
    "X-SIGNATURE v2.1 algorithm is not verified by a sanitized capture; "
    "request signing stays disabled"
)


class RequestSigner(Protocol):
    """Compute the X-SIGNATURE value for a fully assembled request."""

    def signature(self, request: GeelyApiRequest) -> str:
        """Return the signature value for the given request."""
        ...


@dataclass(frozen=True, slots=True)
class TspRequestContext:
    """Static per-installation values used in TSP request headers."""

    device_id: str
    app_version: str
    platform: str = "Android"
    sales_platform: str = "GEELY"
    device_brand: str | None = None
    device_model: str | None = None
    device_os_version: str | None = None
    language: str = "zh_CN"


@dataclass(frozen=True, slots=True)
class VehicleHeaderContext:
    """Per-vehicle header values; both encoded by the app, not by us."""

    vehicle_identifier: str | None = None
    vehicle_series: str | None = None
    vehicle_brand: str | None = None


@dataclass(frozen=True, slots=True)
class GeelyApiRequest:
    """A fully assembled API request ready for a caller-owned session."""

    method: str
    url: str
    headers: dict[str, str]
    body: str | None = None
    endpoint_evidence: str = "unspecified"

    def with_signature(self, signature: str) -> GeelyApiRequest:
        """Return a copy with the X-SIGNATURE header applied."""
        return replace(self, headers={**self.headers, "X-SIGNATURE": signature})


@dataclass(frozen=True, slots=True)
class UnverifiedSigner:
    """Default signer that keeps the protocol gate closed."""

    reason: str = _GATE_MESSAGE

    def signature(self, request: GeelyApiRequest) -> str:
        """Refuse to sign until the algorithm is verified."""
        del request
        raise GeelyProtocolUnavailable(self.reason)


def build_tsp_request(
    endpoint: Endpoint,
    access_token: str,
    context: TspRequestContext,
    signer: RequestSigner,
    vehicle: VehicleHeaderContext | None = None,
    *,
    nonce: str | None = None,
    timestamp_ms: int | None = None,
    query: str = "",
    body: str | None = None,
) -> GeelyApiRequest:
    """Assemble the verified TSP header set; delegate X-SIGNATURE."""
    nonce_value = nonce or str(uuid.uuid4())
    timestamp = time.time_ns() // 1_000_000
    if timestamp_ms is not None:
        timestamp = timestamp_ms
    url = endpoint.url + (f"?{query}" if query else "")

    headers: dict[str, str] = {
        "X-TENANT-ID": TENANT_ID,
        "X-PLATFORM": context.platform,
        "X-SALES-PLATFORM": context.sales_platform,
        "X-APP-ID": APP_ID,
        "X-APP-VERSION": context.app_version,
        "ACCEPT": "application/json; charset=UTF-8",
        "ACCEPT-LANGUAGE": context.language,
        "AUTHORIZATION": access_token,
        "X-API-SIGNATURE-VERSION": X_API_SIGNATURE_VERSION,
        "X-API-SIGNATURE-NONCE": nonce_value,
        "X-TIMESTAMP": str(timestamp),
        "X-DEVICE-ID": context.device_id,
        "X-TSP-PLATFORM": str(TSP_PLATFORM),
        "X-VEHICLE-BRAND": "GEELY",
    }
    if context.device_brand is not None:
        headers["X-DEVICE-BRAND"] = context.device_brand
    if context.device_model is not None:
        headers["X-DEVICE-MODEL"] = context.device_model
    if context.device_os_version is not None:
        headers["X-DEVICE-OS-VERSION"] = context.device_os_version
    if vehicle is not None:
        if vehicle.vehicle_identifier is not None:
            headers["X-VEHICLE-IDENTIFIER"] = vehicle.vehicle_identifier
        if vehicle.vehicle_series is not None:
            headers["X-VEHICLE-SERIES"] = vehicle.vehicle_series
        if vehicle.vehicle_brand is not None:
            headers["X-VEHICLE-BRAND"] = vehicle.vehicle_brand
    if body is not None:
        headers["Content-Type"] = "application/json; charset=UTF-8"

    request = GeelyApiRequest(
        method=endpoint.method,
        url=url,
        headers=headers,
        body=body,
        endpoint_evidence=endpoint.evidence,
    )
    return request.with_signature(signer.signature(request))


def require_verified(endpoint: Endpoint) -> None:
    """Raise the protocol gate for endpoints without live verification."""
    if not endpoint.verified:
        raise GeelyProtocolUnavailable(
            f"endpoint {endpoint.path} is a {endpoint.evidence}; "
            "a live sanitized capture is required before calling it"
        )
