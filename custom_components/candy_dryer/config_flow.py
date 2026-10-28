"""Config flow for the Candy dryer integration."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .client import CandyConnectionError, discover_key
from .const import CONF_KEY, DOMAIN, LOGGER
from .protocol import InvalidStatusError


class CandyDryerConfigFlow(ConfigFlow, domain=DOMAIN):
    """Ask for the dryer address and recover its encryption key."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for the IP address of the dryer."""
        errors: dict[str, str] = {}
        if user_input is not None:
            host = user_input[CONF_HOST].strip()
            self._async_abort_entries_match({CONF_HOST: host})
            try:
                key = await discover_key(async_get_clientsession(self.hass), host)
            except CandyConnectionError:
                errors["base"] = "cannot_connect"
            except InvalidStatusError as err:
                LOGGER.warning("Unexpected answer from %s: %s", host, err)
                errors["base"] = "not_a_dryer"
            else:
                return self.async_create_entry(
                    title="Candy dryer", data={CONF_HOST: host, CONF_KEY: key}
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_HOST): str}),
            errors=errors,
        )
