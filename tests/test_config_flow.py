"""Test the config-flow protocol gate without requiring a full HA install."""

import asyncio
import importlib
import sys
from types import ModuleType


def install_homeassistant_stubs() -> None:
    homeassistant = ModuleType("homeassistant")
    config_entries = ModuleType("homeassistant.config_entries")
    data_entry_flow = ModuleType("homeassistant.data_entry_flow")

    class ConfigFlow:
        def __init_subclass__(cls, *, domain=None, **kwargs):
            del domain
            super().__init_subclass__(**kwargs)

        def async_abort(self, *, reason):
            return {"type": "abort", "reason": reason}

    config_entries.ConfigFlow = ConfigFlow
    data_entry_flow.FlowResult = dict
    homeassistant.config_entries = config_entries
    sys.modules["homeassistant"] = homeassistant
    sys.modules["homeassistant.config_entries"] = config_entries
    sys.modules["homeassistant.data_entry_flow"] = data_entry_flow


def test_config_flow_aborts_without_collecting_input() -> None:
    install_homeassistant_stubs()
    module_name = "custom_components.geely_auto.config_flow"
    sys.modules.pop(module_name, None)
    module = importlib.import_module(module_name)
    flow = module.GeelyAutoConfigFlow()

    result = asyncio.run(flow.async_step_user({"unexpected": "ignored"}))

    assert result == {"type": "abort", "reason": "protocol_samples_required"}
