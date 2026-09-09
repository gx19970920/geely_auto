#!/usr/bin/env python3
"""Drive the local test HA: login -> token -> config flow -> entity assertion.

Usage: python scripts/test_ha_flow.py   (HA test instance on 127.0.0.1:18123)
Credentials: user "geely", password "GeelyTest-2026" (local test instance only).
"""

from __future__ import annotations

import json
import sys
import time
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


def get(path: str, *, token: str | None = None) -> Any:
    """GET JSON from Home Assistant."""
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(BASE + path, headers=headers, method="GET")  # noqa: S310
    with urllib.request.urlopen(req) as resp:  # noqa: S310
        return json.loads(resp.read().decode())


def delete(path: str, *, token: str | None = None) -> Any:
    """DELETE request to Home Assistant."""
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(BASE + path, headers=headers, method="DELETE")  # noqa: S310
    with urllib.request.urlopen(req) as resp:  # noqa: S310
        return json.loads(resp.read().decode())


def main() -> int:
    """Run login -> config flow -> entity verification end to end."""
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
    access_token = token_resp["access_token"]
    print("Access token acquired successfully.")

    # Clean up any existing geely_auto config entries for idempotent test
    existing = get("/api/config/config_entries/entry", token=access_token)
    for entry in existing:
        if entry.get("domain") == "geely_auto":
            eid = entry["entry_id"]
            print(f"Removing existing geely_auto entry: {eid}")
            delete(f"/api/config/config_entries/entry/{eid}", token=access_token)

    # --- Step 1: Start the geely_auto config flow ---
    result = post(
        "/api/config/config_entries/flow",
        {"handler": "geely_auto"},
        token=access_token,
    )
    print("=== CONFIG FLOW STEP 1 (FORM) ===")
    print(json.dumps(result, ensure_ascii=False, indent=1))
    if result.get("type") != "form":
        print("ERROR: Expected form step, got:", result.get("type"))
        return 1

    # --- Step 2: Submit demo mode configuration ---
    flow_id = result["flow_id"]
    submit_result = post(
        f"/api/config/config_entries/flow/{flow_id}",
        {"demo_mode": True},
        token=access_token,
    )
    print("=== CONFIG FLOW STEP 2 (SUBMIT DEMO) ===")
    print(json.dumps(submit_result, ensure_ascii=False, indent=1))
    if submit_result.get("type") != "create_entry":
        print("ERROR: Expected create_entry, got:", submit_result.get("type"))
        return 1

    print("Config entry created successfully! Waiting 3s for entities to load...")
    time.sleep(3)

    # --- Step 3: Verify entity states in Home Assistant ---
    states = get("/api/states", token=access_token)
    vehicle_entities = [
        s
        for s in states
        if any(
            k in s.get("entity_id", "")
            for k in (
                "geely",
                "fuel",
                "xing_yue",
                "vehicle",
                "door",
                "window",
                "climate",
                "charging",
                "odometer",
                "usage",
            )
        )
    ]
    print(f"\nDiscovered {len(vehicle_entities)} vehicle entities:")
    binary_count = 0
    sensor_count = 0
    for entity in vehicle_entities:
        eid = entity.get("entity_id")
        state = entity.get("state")
        friendly = entity.get("attributes", {}).get("friendly_name")
        unit = entity.get("attributes", {}).get("unit_of_measurement", "")
        if eid.startswith("binary_sensor."):
            binary_count += 1
            print(f"  - [BINARY] {eid}: {state} ({friendly})")
        else:
            sensor_count += 1
            print(f"  - [SENSOR] {eid}: {state} {unit} ({friendly})")

    if not vehicle_entities:
        print("WARNING: No vehicle entities found matching vehicle patterns.")
        # Print all states to inspect
        all_ids = [s.get("entity_id") for s in states]
        print(f"All {len(all_ids)} entity IDs:", all_ids[:20])
        return 1

    print(f"\nSummary: {sensor_count} sensors, {binary_count} binary sensors.")
    print("\n[SUCCESS] DOCKER RUNTIME VERIFICATION COMPLETED SUCCESSFULLY!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
