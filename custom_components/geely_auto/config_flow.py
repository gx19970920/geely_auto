"""Config flow for Geely Auto."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant import config_entries

if TYPE_CHECKING:
    from homeassistant.data_entry_flow import FlowResult

from .const import DOMAIN, PROTOCOL_GATE_REASON


class GeelyAutoConfigFlow(
    config_entries.ConfigFlow,
    domain=DOMAIN,
):
    """Stop setup until sanitized protocol samples have been verified."""

    VERSION = 1

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> FlowResult:
        """Explain why setup is not available without requesting credentials."""
        del user_input
        return self.async_abort(reason=PROTOCOL_GATE_REASON)
