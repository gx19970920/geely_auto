"""Diagnostics support with mandatory redaction.

Everything emitted here passes through ``redact_data``; tokens, cookies,
device identifiers, VINs and coordinates never appear in diagnostics.
"""

from __future__ import annotations

from dataclasses import asdict
from typing import TYPE_CHECKING, Any

from .const import DOMAIN
from .redaction import redact_data

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant


async def async_get_diagnostics(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> dict[str, Any]:
    """Return a fully redacted diagnostics payload for one entry."""
    coordinator = hass.data.get(DOMAIN, {}).get(entry.entry_id)
    snapshot = getattr(coordinator, "data", None)

    vehicles: list[dict[str, Any]] = []
    if snapshot is not None:
        for summary in snapshot.summaries:
            state = snapshot.states.get(summary.vin_hash)
            vehicles.append(
                redact_data(
                    {
                        "vin_hash": summary.vin_hash,
                        "brand": summary.brand_code,
                        "model_code": summary.model_code,
                        "engine_type": summary.engine_type,
                        "tsp_platform": summary.tsp_platform,
                        "is_default": summary.is_default,
                        "known_fields": sorted(
                            key
                            for key, value in (
                                asdict(state).items() if state is not None else ()
                            )
                            if value is not None
                        ),
                    }
                )
            )

    payload: dict[str, Any] = redact_data(
        {
            "entry": {
                "entry_id": entry.entry_id,
                "data_keys": sorted(entry.data.keys()),
                "data": entry.data,
            },
            "coordinator": {
                "last_update_success": getattr(
                    coordinator, "last_update_success", False
                ),
                "vehicle_count": len(vehicles),
                "vehicles": vehicles,
            },
        }
    )
    return payload
