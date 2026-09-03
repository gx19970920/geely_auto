"""Protocol endpoint table with explicit evidence classification.

Every endpoint carries an evidence tag:

- ``verified-capture``: observed live in a sanitized MITM capture of the
  logged-in Geely app (method, host, path, and header set all confirmed).
- ``static-candidate``: extracted from APK string analysis; must not be
  called until a live capture verifies it.

Endpoints are data only; nothing in this module performs I/O.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from custom_components.geely_auto.const import (
    EVIDENCE_STATIC_CANDIDATE,
    EVIDENCE_VERIFIED,
)


@dataclass(frozen=True, slots=True)
class Endpoint:
    """One API endpoint plus its evidence classification."""

    base: str
    path: str
    method: str
    evidence: str

    @property
    def url(self) -> str:
        """Return the absolute URL for this endpoint."""
        return f"{self.base}{self.path}"

    @property
    def verified(self) -> bool:
        """Return True only for live-verified endpoints."""
        return self.evidence == EVIDENCE_VERIFIED


GRIC_API_BASE: Final = "https://gric-api.geely.com"

VEHICLE_LIST: Final = Endpoint(
    base=GRIC_API_BASE,
    path="/ms-vehicle-core/api/v1.0/vehicle/favorite-vehicles",
    method="GET",
    evidence=EVIDENCE_VERIFIED,
)

VEHICLE_STATUS_LATEST: Final = Endpoint(
    base=GRIC_API_BASE,
    path="/ms-vehicle-status/api/v2.0/vehicle/status/latest",
    method="GET",
    evidence=EVIDENCE_STATIC_CANDIDATE,
)

VEHICLE_CAPABILITY: Final = Endpoint(
    base=GRIC_API_BASE,
    path="/ms-vehicle-capability-set/api/app/v1/vehicle/capability/available",
    method="GET",
    evidence=EVIDENCE_STATIC_CANDIDATE,
)

ALL_ENDPOINTS: Final[tuple[Endpoint, ...]] = (
    VEHICLE_LIST,
    VEHICLE_STATUS_LATEST,
    VEHICLE_CAPABILITY,
)
