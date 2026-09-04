#!/usr/bin/env python3
"""Drive the local test HA: login -> token -> config flow gate assertion.

Usage: python scripts/test_ha_flow.py   (HA test instance on 127.0.0.1:18123)
Credentials: user "geely", password "GeelyTest-2026" (local test instance only).
"""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

BASE = "http://127.0.0.1:18123"
TOKEN_FILE = Path("ha-config/.ha_test_token")


def post(
    path: str,
    body: dict[str, Any],
    *,
    token: str | None = None,
    form: bool = False,
) -> dict[str, Any]:
    """POST JSON (or form) data and return the parsed JSON response."""
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if form:
        data = urllib.parse.urlencode(body).encode()
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    else:
        data = json.dumps(body).encode()
    req = urllib.request.Request(  # noqa: S310
        BASE + path, data=data, headers=headers, method="POST"
    )
    try:
        with urllib.request.urlopen(req) as resp:  # noqa: S310
            result: dict[str, Any] = json.loads(resp.read().decode())
            return result
    except urllib.error.HTTPError as error:
        payload = error.read().decode()
        raise RuntimeError(f"{path} -> {error.code}: {payload}") from error


def main() -> int:
    """Run the login + gate assertion end to end."""
    client_id = f"{BASE}/"

    flow = post(
        "/auth/login_flow",
        {
            "client_id": client_id,
            "handler": ["homeassistant", None],
            "redirect_uri": f"{client_id}?auth_callback=1",
        },
    )
    print(f"login flow: {flow['flow_id']} step={flow['step_id']}")

    done = post(
        f"/auth/login_flow/{flow['flow_id']}",
        {
            "client_id": client_id,
            "username": "geely",
            "password": "GeelyTest-2026",
        },
    )
    print(f"login result: {done.get('type')}")
    if done.get("type") != "create_entry":
        print(json.dumps(done, ensure_ascii=False, indent=1))
        return 2

    token_resp = post(
        "/auth/token",
        {
            "grant_type": "authorization_code",
            "code": done["result"],
            "client_id": client_id,
        },
        form=True,
    )
    TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
    TOKEN_FILE.write_text(token_resp["refresh_token"], encoding="utf-8")
    saved = len(token_resp["refresh_token"])
    print(f"access token ok; refresh_token saved ({saved} chars)")

    # --- THE GATE TEST: start the geely_auto config flow ---
    result = post(
        "/api/config/config_entries/flow",
        {"handler": "geely_auto"},
        token=token_resp["access_token"],
    )
    print("=== CONFIG FLOW RESULT ===")
    print(json.dumps(result, ensure_ascii=False, indent=1))
    if result.get("type") == "abort" and result.get("reason") == "protocol_samples_required":  # noqa: E501
        print("GATE ASSERTION: PASS (aborted with protocol_samples_required)")
        return 0
    print("GATE ASSERTION: FAIL")
    return 1


if __name__ == "__main__":
    sys.exit(main())
