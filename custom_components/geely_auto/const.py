"""Constants for the Geely Auto integration."""

from typing import Final

DOMAIN: Final = "geely_auto"
PROTOCOL_GATE_REASON: Final = "protocol_samples_required"

CONF_ACCESS_TOKEN: Final = "access_token"  # noqa: S105 - config key name, not a secret
CONF_DEVICE_ID: Final = "device_id"
CONF_APP_VERSION: Final = "app_version"
UPDATE_INTERVAL_SECONDS: Final = 300

# Evidence classes used across the protocol layer.
EVIDENCE_VERIFIED: Final = "verified-capture"
EVIDENCE_STATIC_CANDIDATE: Final = "static-candidate"

# App-level identifiers observed in verified captures. These are static
# application values (not account secrets); they remain constants.
TENANT_ID: Final = "GEELY"
APP_ID: Final = "GEELYCNCH001M0001"  # nosec-secret-scan (static app id)
TSP_PLATFORM: Final = 2
X_API_SIGNATURE_VERSION: Final = "2.1"
