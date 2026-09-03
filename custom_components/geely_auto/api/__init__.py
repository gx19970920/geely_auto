"""Public protocol-layer exports for Geely Auto."""

from .client import GeelyAutoApi
from .endpoints import (
    GRIC_API_BASE,
    VEHICLE_CAPABILITY,
    VEHICLE_LIST,
    VEHICLE_STATUS_LATEST,
    Endpoint,
)
from .exceptions import (
    GeelyAuthError,
    GeelyCommandError,
    GeelyConnectionError,
    GeelyError,
    GeelyProtocolError,
    GeelyProtocolUnavailable,
    GeelyRateLimitError,
)
from .models import (
    TokenBundle,
    VehicleCapabilities,
    VehicleState,
    VehicleSummary,
)
from .parsers import parse_vehicle_list, parse_vehicle_status, vin_hash
from .signing import (
    GeelyApiRequest,
    RequestSigner,
    TspRequestContext,
    UnverifiedSigner,
    VehicleHeaderContext,
    build_tsp_request,
)

__all__ = [
    "GRIC_API_BASE",
    "VEHICLE_CAPABILITY",
    "VEHICLE_LIST",
    "VEHICLE_STATUS_LATEST",
    "Endpoint",
    "GeelyApiRequest",
    "GeelyAuthError",
    "GeelyAutoApi",
    "GeelyCommandError",
    "GeelyConnectionError",
    "GeelyError",
    "GeelyProtocolError",
    "GeelyProtocolUnavailable",
    "GeelyRateLimitError",
    "RequestSigner",
    "TokenBundle",
    "TspRequestContext",
    "UnverifiedSigner",
    "VehicleCapabilities",
    "VehicleHeaderContext",
    "VehicleState",
    "VehicleSummary",
    "build_tsp_request",
    "parse_vehicle_list",
    "parse_vehicle_status",
    "vin_hash",
]
