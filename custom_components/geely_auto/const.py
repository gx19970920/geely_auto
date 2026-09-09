"""Constants for the Geely Auto integration."""

from typing import Final

DOMAIN: Final = "geely_auto"
PROTOCOL_GATE_REASON: Final = "protocol_samples_required"

CONF_ACCESS_TOKEN: Final = "access_token"  # noqa: S105 - config key name, not a secret
CONF_REFRESH_TOKEN: Final = "refresh_token"  # noqa: S105
CONF_DEVICE_ID: Final = "device_id"
CONF_APP_VERSION: Final = "app_version"
CONF_DEMO_MODE: Final = "demo_mode"
CONF_SIGNING_SECRET: Final = "signing_secret"  # noqa: S105
CONF_PHONE: Final = "phone"
CONF_LOGIN_METHOD: Final = "login_method"
CONF_CUSTOM_VEHICLE_NAME: Final = "custom_vehicle_name"
CONF_GEELY_POINTS: Final = "geely_points"
CONF_CHECKIN_PROXY_URL: Final = "checkin_proxy_url"

LOGIN_METHOD_SMS: Final = "sms"
LOGIN_METHOD_TOKEN: Final = "token"  # noqa: S105
LOGIN_METHOD_DEMO: Final = "demo"

DEFAULT_APP_VERSION: Final = "3.54.0"
DEFAULT_CHECKIN_PROXY_URL: Final = "http://127.0.0.1:8899"
UPDATE_INTERVAL_SECONDS: Final = 300

# Evidence classes used across the protocol layer.
EVIDENCE_VERIFIED: Final = "verified-capture"
EVIDENCE_STATIC_CANDIDATE: Final = "static-candidate"

# App-level identifiers observed in verified captures.
TENANT_ID: Final = "GEELY"
APP_ID: Final = "GEELYCNCH001M0001"  # nosec-secret-scan (static app id)
TSP_PLATFORM: Final = 2
X_API_SIGNATURE_VERSION: Final = "2.1"

# Gateway API Keys and Secrets (reverse-engineered from base.apk security libraries)
API_GATEWAY_APP_KEY: Final = "204397973"
API_GATEWAY_APP_SECRET: Final = "nLTrIjIPmri2h3eijwsz9QkR4a5Vdw6q"  # noqa: S105  # nosec-secret-scan
API_GATEWAY_APP_CODE: Final = "geely-app-user"
USER_API_BASE: Final = "https://geely-user-api.geely.com"
TOC_API_BASE: Final = "https://api-gw-toc.geely.com"

# GeeTest captcha configuration
GEETEST_HOST: Final = "captcha4.geely.com"
CAPTCHA_ID: Final = "37c5534e44ee98e72fe04e55a4431f01"
