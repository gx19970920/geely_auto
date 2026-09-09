"""Config flow for Geely Auto."""

from __future__ import annotations

import asyncio
import logging
import re
import socket
import uuid
from typing import TYPE_CHECKING, Any

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import aiohttp_client

from .api.client import GeelyAutoApi
from .api.exceptions import GeelyAuthError, GeelyProtocolError
from .captcha_views import ensure_captcha_views
from .const import (
    CONF_ACCESS_TOKEN,
    CONF_APP_VERSION,
    CONF_CUSTOM_VEHICLE_NAME,
    CONF_DEMO_MODE,
    CONF_DEVICE_ID,
    CONF_LOGIN_METHOD,
    CONF_PHONE,
    CONF_REFRESH_TOKEN,
    DEFAULT_APP_VERSION,
    DOMAIN,
    LOGIN_METHOD_DEMO,
    LOGIN_METHOD_SMS,
    LOGIN_METHOD_TOKEN,
)

if TYPE_CHECKING:
    from homeassistant.data_entry_flow import FlowResult

_LOGGER = logging.getLogger(__name__)

try:
    import voluptuous as vol
except ImportError:

    class _VolStub:
        def Schema(self, schema: Any) -> Any:  # noqa: N802
            return schema

        def Required(self, key: Any, default: Any = None) -> Any:  # noqa: N802, ARG002
            return key

        def Optional(self, key: Any, default: Any = None) -> Any:  # noqa: N802, ARG002
            return key

        def In(self, choices: Any) -> Any:  # noqa: N802
            return choices

    vol = _VolStub()


STEP_USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_LOGIN_METHOD, default=LOGIN_METHOD_SMS): vol.In(
            [LOGIN_METHOD_SMS, LOGIN_METHOD_TOKEN, LOGIN_METHOD_DEMO]
        ),
        vol.Optional(CONF_DEMO_MODE, default=False): bool,
        vol.Optional(CONF_ACCESS_TOKEN, default=""): str,
        vol.Optional(CONF_DEVICE_ID, default=""): str,
        vol.Optional(CONF_APP_VERSION, default=DEFAULT_APP_VERSION): str,
    }
)

STEP_PHONE_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_PHONE): str,
    }
)

STEP_SMS_CODE_SCHEMA = vol.Schema(
    {
        vol.Optional("sms_code", default=""): str,
        vol.Optional("resend_code", default=False): bool,
    }
)

STEP_TOKEN_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_ACCESS_TOKEN): str,
        vol.Optional(CONF_REFRESH_TOKEN, default=""): str,
        vol.Optional(CONF_DEVICE_ID, default=""): str,
        vol.Optional(CONF_APP_VERSION, default=DEFAULT_APP_VERSION): str,
    }
)


class GeelyAutoConfigFlow(
    config_entries.ConfigFlow,
    domain=DOMAIN,
):
    """Handle a config flow for Geely Auto."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize config flow state."""
        self._phone: str = ""
        self._device_id: str = ""
        self._certify_id: str = ""
        self._captcha_data: dict[str, Any] | None = None

    @property
    def _is_reauth(self) -> bool:
        """Check if this is a reauth flow."""
        return bool(self.context.get("source") == config_entries.SOURCE_REAUTH)

    def _get_api(self) -> GeelyAutoApi:
        """Obtain GeelyAutoApi using the HA aiohttp client session."""
        session = aiohttp_client.async_get_clientsession(self.hass)
        return GeelyAutoApi(session=session)

    def _captcha_url(self, flow_id: str) -> str:
        """Construct absolute URL for the GeeTest captcha webview."""
        base: str | None = None
        try:
            from homeassistant.helpers.network import get_url  # noqa: PLC0415

            base = get_url(self.hass, allow_internal=True, allow_external=True)
        except Exception:
            base = None

        if not base:
            try:
                cfg = getattr(self.hass, "config", None)
                if cfg:
                    base = getattr(cfg, "external_url", None) or getattr(
                        cfg, "internal_url", None
                    )
            except Exception:
                base = None

        if not base:
            ip = self._local_ip()
            port = getattr(getattr(self.hass, "config", None), "api_port", 8123) or 8123
            base = f"http://{ip}:{port}"

        return f"{base}/api/geely_auto/captcha?flow_id={flow_id}"

    @staticmethod
    def _local_ip() -> str:
        """Detect local IP address of the host."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            sock.connect(("8.8.8.8", 80))
            return str(sock.getsockname()[0])
        except OSError:
            return "127.0.0.1"
        finally:
            sock.close()

    def _get_captcha_data(self) -> dict[str, Any] | None:
        """Consume captcha result for this flow if available."""
        domain_data = self.hass.data.get(DOMAIN)
        if isinstance(domain_data, dict):
            results = domain_data.get("captcha_results")
            if isinstance(results, dict):
                res = results.pop(self.flow_id, None)
                if isinstance(res, dict):
                    return res
        return None

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> FlowResult:
        """Handle the user configuration step: choose login method."""
        if hasattr(self, "hass") and self.hass:
            ensure_captcha_views(self.hass)

        if user_input is not None:
            if (
                user_input.get("demo_mode")
                or user_input.get(CONF_LOGIN_METHOD) == LOGIN_METHOD_DEMO
            ):
                return await self.async_step_demo()
            if user_input.get(CONF_ACCESS_TOKEN):
                return await self.async_step_token(user_input)
            if user_input.get(CONF_LOGIN_METHOD) == LOGIN_METHOD_TOKEN:
                return await self.async_step_token()
            if user_input.get(CONF_LOGIN_METHOD) == LOGIN_METHOD_SMS:
                return await self.async_step_sms_phone()
            if user_input.get(CONF_PHONE):
                return await self.async_step_sms_phone(user_input)

        return self.async_show_menu(
            step_id="user",
            menu_options=["sms", "token", "demo"],
        )

    async def async_step_sms(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Route to SMS phone step."""
        return await self.async_step_sms_phone(user_input)

    async def async_step_demo(
        self, user_input: dict[str, Any] | None = None  # noqa: ARG002
    ) -> FlowResult:
        """Create entry in demo mode directly."""
        return self._create_entry_from_input(
            demo=True,
            access_token="",
        )

    async def async_step_sms_phone(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Step 1: Enter mobile phone number."""
        if hasattr(self, "hass") and self.hass:
            ensure_captcha_views(self.hass)

        if user_input is not None:
            raw_phone = str(user_input[CONF_PHONE]).strip()
            clean_phone = re.sub(r"[^\d]", "", raw_phone)
            if clean_phone.startswith("86") and len(clean_phone) == 13:
                clean_phone = clean_phone[2:]
            self._phone = clean_phone
            self._device_id = uuid.uuid4().hex[:16]
            return await self.async_step_sms_captcha()

        return self.async_show_form(
            step_id="sms_phone",
            data_schema=STEP_PHONE_SCHEMA,
        )

    async def async_step_sms_captcha(
        self,
        user_input: dict[str, Any] | None = None,  # noqa: ARG002
    ) -> FlowResult:
        """Step 2: External GeeTest slide verification step."""
        if hasattr(self, "hass") and self.hass:
            ensure_captcha_views(self.hass)

        captcha_data = self._get_captcha_data()
        if captcha_data:
            self._captcha_data = captcha_data
            return self.async_external_step_done(next_step_id="sms_code")

        await asyncio.sleep(0.05)
        return self.async_external_step(
            step_id="sms_captcha",
            url=self._captcha_url(self.flow_id),
        )

    async def async_step_sms_code(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Step 3: Validate captcha, send SMS, and verify SMS code."""
        errors: dict[str, str] = {}
        api = self._get_api()

        if user_input is not None:
            if user_input.get("resend_code") or not str(user_input.get("sms_code", "")).strip():
                _LOGGER.info("User requested new SMS code, redirecting to captcha verification")
                self._captcha_data = None
                self._certify_id = ""
                return await self.async_step_sms_captcha()

            result = await self._handle_sms_login_submit(api, user_input, errors)
            if result is not None:
                return result

        elif self._captcha_data:
            await self._handle_captcha_data(api, errors)

        return self.async_show_form(
            step_id="sms_code",
            data_schema=STEP_SMS_CODE_SCHEMA,
            errors=errors,
        )

    async def _handle_sms_login_submit(
        self,
        api: GeelyAutoApi,
        user_input: dict[str, Any],
        errors: dict[str, str],
    ) -> FlowResult | None:
        """Handle SMS code form submission."""
        raw_code = str(user_input.get("sms_code", "")).strip()
        sms_code = re.sub(r"[^\d]", "", raw_code)
        if len(sms_code) != 6:
            errors["base"] = "sms_code_format"
            return None

        _LOGGER.info(
            "Submitting SMS verification code login: phone=***%s, code_len=%d, certify_id=%s, device_id=%s",
            self._phone[-4:] if len(self._phone) >= 4 else self._phone,
            len(sms_code),
            self._certify_id[:8] if self._certify_id else "none",
            self._device_id[:8] if self._device_id else "none",
        )
        try:
            tokens = await api.sms_login(
                phone=self._phone,
                sms_code=sms_code,
                certify_id=self._certify_id,
                device_id=self._device_id,  # nosec-secret-scan
            )
            access_token = tokens["access_token"]
            refresh_token = tokens.get("refresh_token", "")

            title = f"吉利汽车 ({self._phone[-4:]})"
            vin = ""
            try:
                vehicles = await api.get_vehicles(access_token)
                if vehicles:
                    model = vehicles[0].model_name or vehicles[0].series_name
                    if model:
                        title = f"吉利汽车 ({model})"
                    vin = vehicles[0].vin
            except Exception as err:
                _LOGGER.debug("Vehicle info fetch after login: %s", err)

            if vin:
                await self.async_set_unique_id(vin)
                self._abort_if_unique_id_configured()

            return self.async_create_entry(
                title=title,
                data={
                    CONF_DEMO_MODE: False,
                    CONF_ACCESS_TOKEN: access_token,  # nosec-secret-scan
                    CONF_REFRESH_TOKEN: refresh_token,  # nosec-secret-scan
                    CONF_DEVICE_ID: self._device_id,  # nosec-secret-scan
                    CONF_APP_VERSION: DEFAULT_APP_VERSION,
                    CONF_PHONE: self._phone,
                },
            )
        except GeelyAuthError as err:
            _LOGGER.exception("SMS login authentication rejected: %s", err)
            err_msg = str(err)
            if any(k in err_msg for k in ("已失效", "过期", "expired", "expire")):
                errors["base"] = "sms_code_expired"
            elif any(k in err_msg for k in ("验证码错误", "wrong", "invalid")):
                errors["base"] = "sms_code_wrong"
            else:
                errors["base"] = "invalid_sms_code"
        except GeelyProtocolError as err:
            _LOGGER.exception("SMS login protocol error: %s", err)
            errors["base"] = "cannot_connect"
        except Exception:
            _LOGGER.exception("Unexpected error during SMS login")
            errors["base"] = "unknown"
        return None

    async def _handle_captcha_data(
        self,
        api: GeelyAutoApi,
        errors: dict[str, str],
    ) -> None:
        """Process incoming GeeTest captcha result and request SMS code."""
        captcha_data = self._captcha_data
        self._captcha_data = None
        if not captcha_data:
            return
        _LOGGER.info(
            "Processing captcha result: lot_number=%s, phone=***%s",
            captcha_data.get("lot_number"),
            self._phone[-4:] if len(self._phone) >= 4 else self._phone,
        )
        try:
            self._certify_id = await api.validate_geetest(
                lot_number=captcha_data["lot_number"],
                captcha_output=captcha_data["captcha_output"],
                pass_token=captcha_data["pass_token"],
                gen_time=captcha_data["gen_time"],
                device_id=self._device_id,  # nosec-secret-scan
            )
            _LOGGER.info("GeeTest validation succeeded, certifyId=%s", self._certify_id)
            await api.send_sms_code(
                phone=self._phone,
                certify_id=self._certify_id,
                device_id=self._device_id,  # nosec-secret-scan
            )
            _LOGGER.info("SMS code successfully dispatched to ***%s", self._phone[-4:])
        except GeelyAuthError as err:
            _LOGGER.exception("GeeTest verification failed: %s", err)
            errors["base"] = "captcha_failed"
        except GeelyProtocolError as err:
            _LOGGER.exception("Failed to send SMS code: %s", err)
            errors["base"] = "sms_send_failed"
        except Exception:
            _LOGGER.exception("Unexpected error validating captcha / sending SMS")
            errors["base"] = "unknown"

    async def async_step_token(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle token login step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            access_token = str(user_input.get(CONF_ACCESS_TOKEN, "")).strip()
            if not access_token:
                errors["base"] = "invalid_auth"
            else:
                return self._create_entry_from_input(
                    demo=False,
                    access_token=access_token,  # nosec-secret-scan
                    refresh_token=str(user_input.get(CONF_REFRESH_TOKEN, "")).strip(),  # nosec-secret-scan
                    device_id=str(user_input.get(CONF_DEVICE_ID, "")).strip(),  # nosec-secret-scan
                    app_version=str(user_input.get(CONF_APP_VERSION, "")).strip(),
                )

        return self.async_show_form(
            step_id="token",
            data_schema=STEP_TOKEN_SCHEMA,
            errors=errors,
        )

    def _create_entry_from_input(
        self,
        *,
        demo: bool,
        access_token: str,
        refresh_token: str = "",
        device_id: str = "",
        app_version: str = "",
    ) -> FlowResult:
        """Construct the config entry result."""
        dev_id = device_id or str(uuid.uuid4())
        version = app_version or DEFAULT_APP_VERSION
        title = "吉利汽车 (星越L演示)" if demo else f"吉利汽车 ({dev_id[:8]})"
        return self.async_create_entry(
            title=title,
            data={
                CONF_DEMO_MODE: demo,
                CONF_ACCESS_TOKEN: access_token,  # nosec-secret-scan
                CONF_REFRESH_TOKEN: refresh_token,  # nosec-secret-scan
                CONF_DEVICE_ID: dev_id,  # nosec-secret-scan
                CONF_APP_VERSION: version,
            },
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Create the options flow."""
        return GeelyAutoOptionsFlowHandler(config_entry)


class GeelyAutoOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options flow for Geely Auto integration."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage integration options (e.g. custom vehicle name)."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current_name = (
            self.config_entry.options.get(CONF_CUSTOM_VEHICLE_NAME)
            or self.config_entry.data.get(CONF_CUSTOM_VEHICLE_NAME)
            or "星越L·东方曜"
        )
        schema = vol.Schema(
            {
                vol.Optional(CONF_CUSTOM_VEHICLE_NAME, default=current_name): str,
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
