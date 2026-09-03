"""Pure runtime layer: token, API and snapshot handling without HA coupling.

The runtime keeps the protocol gate explicit: :class:`GeelyAutoGateError`
signals that operations were stopped by the evidence gate, which the HA
coordinator surfaces as "unavailable (protocol gate)".
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from custom_components.geely_auto.api.exceptions import GeelyProtocolUnavailable

if TYPE_CHECKING:
    from custom_components.geely_auto.api.client import GeelyAutoApi
    from custom_components.geely_auto.api.models import (
        VehicleState,
        VehicleSummary,
    )
    from custom_components.geely_auto.api.signing import TspRequestContext


class GeelyAutoGateError(RuntimeError):
    """Raised when an operation is stopped by the protocol evidence gate."""


@dataclass(frozen=True, slots=True)
class VehicleSnapshot:
    """One coherent fetch of vehicles and their latest known states."""

    summaries: tuple[VehicleSummary, ...]
    states: dict[str, VehicleState]

    @property
    def gate_closed(self) -> bool:
        """Whether this snapshot is a placeholder from a closed gate."""
        return False


@dataclass(frozen=True, slots=True)
class GateSnapshot(VehicleSnapshot):
    """Placeholder snapshot produced while the protocol gate is closed."""

    @property
    def gate_closed(self) -> bool:
        """Always True for gate placeholders."""
        return True


class GeelyAutoRuntime:
    """Own the API instance and produce coherent vehicle snapshots."""

    def __init__(
        self,
        api: GeelyAutoApi,
        access_token: str | None,
        context: TspRequestContext | None,
    ) -> None:
        """Store the collaborators; tokens may be absent while gated."""
        self._api = api
        self._access_token = access_token  # nosec-secret-scan (parameter passthrough)
        self._context = context

    @property
    def gate_closed(self) -> bool:
        """True while no verified signer/context exists."""
        return self._access_token is None or self._context is None

    async def fetch_snapshot(self) -> VehicleSnapshot:
        """Fetch vehicles and states, or return a gate placeholder."""
        if self.gate_closed:
            return GateSnapshot(summaries=(), states={})
        try:
            summaries = await self._api.get_vehicles(self._access_token or "")
        except GeelyProtocolUnavailable as error:
            raise GeelyAutoGateError(str(error)) from error
        states: dict[str, VehicleState] = {}
        return VehicleSnapshot(summaries=summaries, states=states)
