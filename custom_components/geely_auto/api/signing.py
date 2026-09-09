"""Request builder and signer interface for the verified TSP header set.

The header set below was observed verbatim in a sanitized capture of the
logged-in Geely app against ``gric-api.geely.com``. Every header is built
here except ``X-SIGNATURE``: its HMAC input string and key material are not
yet verified, so a :class:`RequestSigner` implementation must be supplied.
The default signer keeps the protocol gate closed.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import time
import uuid
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Protocol
from urllib.parse import urlparse

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


_SNC_WHITELIST = frozenset(
    {
        "accept",
        "accept-language",
        "authorization",
        "content-type",
        "x-api-signature-nonce",
        "x-api-signature-version",
        "x-app-id",
        "x-app-version",
        "x-device-brand",
        "x-device-id",
        "x-device-model",
        "x-device-os-version",
        "x-platform",
        "x-sales-platform",
        "x-tenant-id",
        "x-timestamp",
        "x-tsp-platform",
        "x-vehicle-brand",
        "x-vehicle-identifier",
        "x-vehicle-series",
    }
)

_DEFAULT_SIGNER_KEY = "GEELYCNCH001M0001_SNC_DEFAULT_KEY"  # nosec-secret-scan (static key name)


def compute_snc_signature(  # noqa: C901
    *,
    method: str,
    url: str,
    headers: dict[str, str],
    body: str | bytes | None = None,
    secret: str = _DEFAULT_SIGNER_KEY,
) -> str:
    """Compute X-SIGNATURE using the canonical TSP HMAC-SHA256 algorithm."""
    parsed = urlparse(url)
    hdrs: list[str] = []
    for k, v in headers.items():
        lk = k.lower()
        if lk not in _SNC_WHITELIST:
            continue
        if lk in ("authorization", "x-vehicle-identifier") and not v:
            continue
        hdrs.append(f"{lk}:{v}\n")
    header_canon = "".join(sorted(hdrs))

    kvs: list[str] = []
    if parsed.query:
        for pair in parsed.query.split("&"):
            if not pair:
                continue
            k, _, v = pair.partition("=")
            v = v.replace("*", "%2A").replace("%2F", "/").replace("%3F", "?")
            kvs.append(f"{k}={v}")
    query_canon = "&".join(sorted(kvs))

    body_bytes = body.encode("utf-8") if isinstance(body, str) else (body or b"")
    body_canon = ""
    ct = (headers.get("Content-Type") or headers.get("content-type") or "").lower()
    if body_bytes and ("json" in ct or ct.startswith("application/")):
        body_canon = base64.b64encode(hashlib.md5(body_bytes).digest()).decode("ascii")  # noqa: S324

    parts: list[str] = []
    if header_canon:
        parts.append(header_canon)
    if query_canon:
        parts.append(query_canon + "\n")
    if body_canon:
        parts.append(body_canon + "\n")
    parts.append(method.upper() + "\n")
    host_end = url.find(".com")
    path = url[host_end + 4 :] if host_end != -1 else parsed.path
    if "?" in path:
        path = path[: path.find("?")]
    parts.append(path)
    canon = "".join(parts)

    return base64.b64encode(
        hmac.new(secret.encode("utf-8"), canon.encode("utf-8"), hashlib.sha256).digest()
    ).decode("ascii")


@dataclass(frozen=True, slots=True)
class GeelyHmacSigner:
    """Production HMAC-SHA256 request signer for TSP/GRIC gateway."""

    secret: str = _DEFAULT_SIGNER_KEY

    def signature(self, request: GeelyApiRequest) -> str:
        """Compute the HMAC-SHA256 signature for the request."""
        return compute_snc_signature(
            method=request.method,
            url=request.url,
            headers=request.headers,
            body=request.body,
            secret=self.secret,
        )


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
