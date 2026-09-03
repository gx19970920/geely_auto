"""Pytest fixtures and early Home Assistant stub installation.

The stubs must be installed before any integration module import: importing
``custom_components.geely_auto.api`` executes the package parent, which
imports ``homeassistant`` at module level (as real integrations do).
"""

from __future__ import annotations

from tests.ha_stubs import install_homeassistant_stubs

install_homeassistant_stubs()
