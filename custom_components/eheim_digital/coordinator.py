"""Eheim Digital DataUpdateCoordinator."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api_client import EheimDigitalAPIClient, EheimDigitalError
from .const import DOMAIN, LOGGER, UPDATE_INTERVAL


class EheimDigitalDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Class to manage fetching EHEIM Digital data."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        api_client: EheimDigitalAPIClient,
    ) -> None:
        """Initialize."""
        self.api_client = api_client
        self.entry = entry
        update_interval = timedelta(seconds=UPDATE_INTERVAL)
        self.devices = []

        super().__init__(hass, LOGGER, name=DOMAIN, update_interval=update_interval)
        # hass.async_create_task(self._async_update_data())

    async def _async_update_data(self) -> dict[str, Any]:
        """Update data via API."""
        all_device_data = {}
        LOGGER.debug("COORDINATOR: Starting data update")
        num_devices = len(self.devices)
        LOGGER.debug(f"COORDINATOR: Number of devices: {num_devices}")

        try:
            LOGGER.debug(
                "COORDINATOR: Calling API Client to update data in Coordinator"
            )
            for device in self.devices:
                LOGGER.debug(f"COORDINATOR: Device: {device}")
                device_data = await self.api_client.get_device_data(device)
                all_device_data[device.mac] = device_data
                LOGGER.debug(
                    f"COORDINATOR: Device {device} data in Coordinator: {device_data}"
                )
        except EheimDigitalError as error:
            self.last_update_success = False
            LOGGER.error(
                f"COORDINATOR: Error fetching data for device {device}: {error}"
            )
            raise UpdateFailed(error) from error
        LOGGER.debug(
            "COORDINATOR: Final aggregated data in Coordinator: {all_device_data}"
        )

        return all_device_data
