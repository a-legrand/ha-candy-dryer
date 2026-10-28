"""Candy dryer integration: local control of Candy Simply-Fi tumble dryers."""

from __future__ import annotations

from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .client import CandyDryerClient
from .const import CONF_KEY
from .coordinator import CandyDryerConfigEntry, CandyDryerCoordinator

PLATFORMS = [Platform.BINARY_SENSOR, Platform.BUTTON, Platform.SELECT, Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: CandyDryerConfigEntry) -> bool:
    """Set up the dryer from a config entry."""
    client = CandyDryerClient(
        async_get_clientsession(hass), entry.data[CONF_HOST], entry.data[CONF_KEY]
    )
    coordinator = CandyDryerCoordinator(hass, entry, client)
    # A switched-off dryer is not a setup failure: the first poll reports it off.
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: CandyDryerConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
