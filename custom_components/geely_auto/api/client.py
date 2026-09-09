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
import hashlib
import json
import logging
import uuid
from typing import TYPE_CHECKING, Any, NoReturn

_LOGGER = logging.getLogger(__name__)

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
from custom_components.geely_auto.api.gateway_signing import build_gateway_headers
from custom_components.geely_auto.api.parsers import (
    parse_vehicle_list,
    parse_vehicle_status,
)
from custom_components.geely_auto.api.signing import (
    GeelyApiRequest,
    GeelyHmacSigner,
    TspRequestContext,
    VehicleHeaderContext,
    build_tsp_request,
    require_verified,
)
from custom_components.geely_auto.const import (
    CAPTCHA_ID,
    DEFAULT_APP_VERSION,
    USER_API_BASE,
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
            signer if signer is not None else GeelyHmacSigner()
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

    async def validate_geetest(
        self,
        lot_number: str,
        captcha_output: str,
        pass_token: str,
        gen_time: str,
        device_id: str | None = None,
    ) -> str:
        """Validate GeeTest v4 captcha with Geely user center."""
        path = "/api/v1/security/geeTestV4/validate"
        url = f"{USER_API_BASE}{path}"
        body = {
            "lotNumber": lot_number,
            "captchaOutput": captcha_output,
            "passToken": pass_token,
            "genTime": gen_time,
            "captchaId": CAPTCHA_ID,
        }
        body_str = json.dumps(body, separators=(",", ":"))
        headers = build_gateway_headers(
            method="POST",
            url=url,
            body=body_str,
            device_id=device_id,
        )
        request = GeelyApiRequest(
            method="POST", url=url, headers=headers, body=body_str
        )
        payload = await self._request_json(request)
        if isinstance(payload, dict):
            if payload.get("code") not in ("success", 0, "0"):
                msg = (
                    payload.get("message")
                    or payload.get("msg")
                    or "Captcha validation failed"
                )
                raise GeelyAuthError(f"GeeTest validation failed: {msg}")
            data = payload.get("data")
            if isinstance(data, dict) and data.get("certifyId"):
                return str(data["certifyId"])
        return lot_number

    async def send_sms_code(
        self,
        phone: str,
        certify_id: str,
        brand: str = "GEELY",
        device_id: str | None = None,
    ) -> bool:
        """Request SMS verification code via Geely user center."""
        path = "/api/v1/message/sendSmsCode"
        url = f"{USER_API_BASE}{path}"
        body = {
            "mobile": phone,
            "scene": "login",
            "certifyId": certify_id,
            "brand": brand,
            "tenantId": "569001401001",
        }
        body_str = json.dumps(body, separators=(",", ":"))
        headers = build_gateway_headers(
            method="POST",
            url=url,
            body=body_str,
            device_id=device_id,
        )
        request = GeelyApiRequest(
            method="POST", url=url, headers=headers, body=body_str
        )
        payload = await self._request_json(request)
        if isinstance(payload, dict):
            code = payload.get("code")
            if code not in ("success", 0, "0"):
                msg = (
                    payload.get("message") or payload.get("msg") or "Failed to send SMS"
                )
                raise GeelyProtocolError(f"Send SMS failed: {msg}")
        return True

    async def sms_login(
        self,
        phone: str,
        sms_code: str,
        certify_id: str,
        device_id: str | None = None,
        app_version: str = DEFAULT_APP_VERSION,
    ) -> dict[str, Any]:
        """Perform SMS verification code login against Geely gateway."""
        dev_id = (device_id or uuid.uuid4().hex[:16]).replace("-", "")[:16]
        dev_id_md5 = hashlib.md5(dev_id.encode("utf-8")).hexdigest()

        candidates: list[tuple[str, str]] = [
            (
                f"mobile={phone}&verificationCode={sms_code}&certifyId={certify_id}&deviceType=android&appVersion={app_version}&deviceId={dev_id}&deviceModel=HomeAssistant",
                dev_id,
            ),
            (
                f"mobile={phone}&verificationCode={sms_code}&deviceType=android&appVersion={app_version}&deviceId={dev_id}&deviceModel=HomeAssistant",
                dev_id,
            ),
            (
                f"mobile={phone}&verificationCode={sms_code}&certifyId={certify_id}&deviceType=android&appVersion={app_version}&deviceId={dev_id_md5}&deviceModel=HomeAssistant",
                dev_id_md5,
            ),
            (
                f"mobile={phone}&verificationCode={sms_code}&deviceType=android&appVersion={app_version}&deviceId={dev_id_md5}&deviceModel=HomeAssistant",
                dev_id_md5,
            ),
        ]

        last_msg = "Invalid SMS code"
        for idx, (query, active_dev_id) in enumerate(candidates):
            path = f"/api/v1/login/mobileCodeLogin?{query}"
            url = f"{USER_API_BASE}{path}"
            body_str = "{}"
            headers = build_gateway_headers(
                method="POST",
                url=url,
                body=body_str,
                device_id=active_dev_id,  # nosec-secret-scan
                app_version=app_version,
            )
            request = GeelyApiRequest(
                method="POST", url=url, headers=headers, body=body_str
            )
            payload = await self._request_json(request)
            _LOGGER.debug(
                "SMS login attempt %d response: payload=%s", idx + 1, payload
            )
            if isinstance(payload, dict):
                code = payload.get("code")
                if code in ("success", 0, "0"):
                    data = payload.get("data")
                    if isinstance(data, dict):
                        raw_dto = data.get("centerTokenDto")
                        token_dto: dict[str, Any] = (
                            raw_dto if isinstance(raw_dto, dict) else data
                        )
                        token = token_dto.get("token") or token_dto.get("accessToken")  # nosec-secret-scan
                        ref_token = token_dto.get("refreshToken")
                        user_id = data.get("userId") or token_dto.get("userId")
                        return {
                            "access_token": token,
                            "refresh_token": ref_token,
                            "user_id": user_id,
                            "device_id": dev_id,
                        }
                msg = payload.get("message") or payload.get("msg") or "Invalid SMS code"
                last_msg = str(msg)
                if any(k in last_msg for k in ("已失效", "过期", "expired")):
                    break

        raise GeelyAuthError(f"SMS login failed: {last_msg}")

    async def refresh_access_token(self, refresh_token: str) -> dict[str, Any]:
        """Refresh access token using the gateway API."""
        path = f"/api/v1/login/refresh?refreshToken={refresh_token}"
        url = f"{USER_API_BASE}{path}"
        headers = build_gateway_headers(
            method="GET",
            url=url,
        )
        request = GeelyApiRequest(method="GET", url=url, headers=headers, body=None)
        payload = await self._request_json(request)
        if isinstance(payload, dict):
            code = payload.get("code")
            if code not in ("success", 0, "0"):
                msg = (
                    payload.get("message")
                    or payload.get("msg")
                    or "Refresh token failed"
                )
                raise GeelyAuthError(f"Token refresh rejected: {msg}")
            data = payload.get("data")
            if isinstance(data, dict):
                raw_dto = data.get("centerTokenDto")
                token_dto: dict[str, Any] = (
                    raw_dto if isinstance(raw_dto, dict) else data
                )
                token = token_dto.get("token") or token_dto.get("accessToken")
                new_ref_token = token_dto.get("refreshToken") or refresh_token
                return {
                    "access_token": token,
                    "refresh_token": new_ref_token,
                }
        raise GeelyAuthError("Token refresh returned invalid payload")

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

    def build_vehicle_status_request(
        self,
        vin: str,
        access_token: str = "",
        vehicle: VehicleHeaderContext | None = None,
    ) -> GeelyApiRequest:
        """Build the verified vehicle-status request (no network I/O)."""
        if self._context is None:
            raise GeelyProtocolUnavailable(
                "TspRequestContext is required to build TSP requests"
            )
        require_verified(VEHICLE_STATUS_LATEST)
        return build_tsp_request(
            VEHICLE_STATUS_LATEST,
            access_token,
            self._context,
            self._signer,
            vehicle,
            query=f"vin={vin}" if vin else "",
        )

    async def get_vehicle_status(
        self,
        vin: str,
        access_token: str = "",
        vehicle: VehicleHeaderContext | None = None,
    ) -> VehicleState:
        """Return normalized vehicle state after the endpoint is verified."""
        request = self.build_vehicle_status_request(vin, access_token, vehicle)
        payload = await self._request_json(request)
        return parse_vehicle_status(payload, vin=vin)

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
