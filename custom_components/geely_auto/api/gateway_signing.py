"""Alibaba Cloud API Gateway request signer for Geely user and toc APIs."""

from __future__ import annotations

import base64
import hashlib
import hmac
import uuid
from datetime import UTC, datetime
from urllib.parse import urlparse

from custom_components.geely_auto.const import (
    API_GATEWAY_APP_CODE,
    API_GATEWAY_APP_KEY,
    API_GATEWAY_APP_SECRET,
    DEFAULT_APP_VERSION,
)

_DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
_MONTHS = [
    "Jan",
    "Feb",
    "Mar",
    "Apr",
    "May",
    "Jun",
    "Jul",
    "Aug",
    "Sep",
    "Oct",
    "Nov",
    "Dec",
]


def format_gmt_date_and_timestamp() -> tuple[str, str]:
    """Format GMT date and millisecond timestamp for API Gateway."""
    now = datetime.now(tz=UTC)
    day_name = _DAYS[now.weekday()]
    month_name = _MONTHS[now.month - 1]
    date_str = (
        f"{day_name}, {now.day:02d} {month_name} {now.year} "
        f"{now.hour:02d}:{now.minute:02d}:{now.second:02d} GMT"
    )
    timestamp = str(int(now.replace(microsecond=0).timestamp()) * 1000)
    return date_str, timestamp


def calculate_content_md5(body: str | bytes | None) -> str:
    """Calculate Content-MD5 header value."""
    if not body:
        return ""
    body_bytes = body.encode("utf-8") if isinstance(body, str) else body
    md5_hash = hashlib.md5(body_bytes).digest()  # noqa: S324 - required by API Gateway
    return base64.b64encode(md5_hash).decode("utf-8")


def calculate_gateway_signature(
    *,
    method: str,
    path: str,
    headers: dict[str, str],
    signature_headers: list[str],
    secret: str = API_GATEWAY_APP_SECRET,
    accept: str = "application/json; charset=utf-8",
    content_type: str = "application/json; charset=utf-8",
    date: str = "",
    content_md5: str = "",
) -> str:
    """Compute x-ca-signature using Alibaba Cloud API Gateway algorithm."""
    # Build StringToSign: Method + Accept + Content-MD5 + Content-Type + Date
    # followed by ordered headers and path.
    order = sorted(signature_headers)
    header_lines = "".join(f"{h}:{headers.get(h, '')}\n" for h in order)
    string_to_sign = (
        f"{method.upper()}\n"
        f"{accept}\n"
        f"{content_md5}\n"
        f"{content_type}\n"
        f"{date}\n"
        f"{header_lines}"
        f"{path}"
    )

    signature = hmac.new(
        secret.encode("utf-8"),
        string_to_sign.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    return base64.b64encode(signature).decode("utf-8")


def build_gateway_headers(
    *,
    method: str,
    url: str,
    body: str | None = None,
    app_key: str = API_GATEWAY_APP_KEY,
    app_secret: str = API_GATEWAY_APP_SECRET,
    app_code: str = API_GATEWAY_APP_CODE,
    token: str | None = None,
    user_id: str | None = None,
    device_id: str | None = None,
    app_version: str = DEFAULT_APP_VERSION,
) -> dict[str, str]:
    """Assemble all headers and compute x-ca-signature for an API Gateway request."""
    parsed = urlparse(url)
    path = parsed.path
    if parsed.query:
        sorted_params = sorted(parsed.query.split("&"))
        path += f"?{'&'.join(sorted_params)}"

    date_str, timestamp = format_gmt_date_and_timestamp()
    nonce = str(uuid.uuid4())
    content_md5 = calculate_content_md5(body) if body else ""
    accept = "application/json; charset=utf-8"
    content_type = "application/json; charset=utf-8"
    dev_sn = (device_id or uuid.uuid4().hex[:16]).replace("-", "")[:16]

    # Signature header list (alphabetical order in StringToSign)
    sig_headers_list = ["x-ca-appcode", "x-ca-key", "x-ca-nonce", "x-ca-timestamp"]
    if user_id:
        sig_headers_list.append("gl_user_id")

    # Initial headers
    headers: dict[str, str] = {
        "accept": accept,
        "content-type": content_type,
        "date": date_str,
        "x-ca-key": app_key,
        "x-ca-nonce": nonce,
        "x-ca-timestamp": timestamp,
        "x-ca-appcode": app_code,
        "x-ca-signature-headers": ",".join(sig_headers_list),
        "ca_version": "1",
        "usetoken": "1",
        "user-agent": "okhttp/4.9.3",
        "devicesn": dev_sn,
        "deviceSN": dev_sn,
        "tenantid": "569001401001",
        "appId": "geely-app",
        "appVersion": app_version,
        "platform": "Android",
        "Cache-Control": "no-cache",
        "Connection": "Keep-Alive",
        "Accept-Encoding": "gzip",
    }
    if content_md5:
        headers["content-md5"] = content_md5
    if user_id:
        headers["gl_user_id"] = user_id
    if token:
        headers["token"] = token
        headers["x-refresh-token"] = "true"

    signature = calculate_gateway_signature(
        method=method,
        path=path,
        headers=headers,
        signature_headers=sig_headers_list,
        secret=app_secret,
        accept=accept,
        content_type=content_type,
        date=date_str,
        content_md5=content_md5,
    )
    headers["x-ca-signature"] = signature
    return headers
