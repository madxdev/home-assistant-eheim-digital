"""Adds config flow for eheim_digital."""

from __future__ import annotations

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_IP_ADDRESS

from .api_client import EheimDigitalAPIClient, EheimDigitalError
from .const import DOMAIN, LOGGER


class EheimDigitalFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for eheim_digital."""

    VERSION = 1

    async def async_step_user(
        self,
        user_input: dict | None = None,
    ) -> config_entries.FlowResult:
        """Handle a flow initialized by the user."""
        LOGGER.debug("User step initiated")
        errors = {}
        if user_input is not None:
            LOGGER.debug("User input received: %s", user_input)
            try:
                await self._test_host_connection(host=user_input[CONF_IP_ADDRESS])
                LOGGER.debug("Connection successful, creating entry")
                return self.async_create_entry(
                    title=user_input[CONF_IP_ADDRESS], data=user_input
                )
            except EheimDigitalError:
                LOGGER.warning("Communication error with host")
                errors["base"] = "communication_error"

        schema = vol.Schema(
            {
                vol.Required(CONF_IP_ADDRESS): str,
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            errors=errors,
        )

    async def _test_host_connection(self, host: str) -> None:
        """Test the connection to the given host."""
        LOGGER.debug(f"Testing host connection: {host}")
        api_client = EheimDigitalAPIClient(host, "api", "admin")
        devices = await api_client.get(host, "devicelist")
        if not devices:
            raise EheimDigitalError("No devices find on host")
        LOGGER.debug(f"Connected to device {devices}")
        # Perform other tests here if needed
        await api_client.close()
        LOGGER.debug("Host connection test completed")
