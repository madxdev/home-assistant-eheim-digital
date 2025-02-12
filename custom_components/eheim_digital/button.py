"""Platform for Button integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.button import (
    ButtonDeviceClass,
    ButtonEntity,
    ButtonEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import EheimDigitalDataUpdateCoordinator
from .api_client import EheimDigitalError
from .const import DOMAIN, LOGGER
from .devices import EheimDevice


@dataclass
class EheimButtonDescriptionMixin:
    """Mixin for Eheim button."""

    manual_feed_fn: Callable[[EheimDevice, EheimDigitalDataUpdateCoordinator], None]


@dataclass
class EheimButtonDescription(ButtonEntityDescription, EheimButtonDescriptionMixin):
    """Class describing Eheim button entities."""

    attr_fn: Callable[[dict[str, Any]], dict[str, StateType]] = lambda _: {}


BUTTON_DESCRIPTIONS: tuple[EheimButtonDescription, ...] = (
    EheimButtonDescription(
        key="manual_feed",
        name="Feed Now",
        device_class=ButtonDeviceClass.RESTART,
        manual_feed_fn=lambda device,
        coordinator: coordinator.api_client.feeder_manual_feed(device),
    ),
)

BUTTON_GROUPS = {
    # Define button groups similar to SENSOR_GROUPS
    "feeder": ["manual_feed"],
}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Add EheimDevice entities from a config_entry."""
    LOGGER.debug("Setting up Eheim Digital Button platform")

    coordinator: EheimDigitalDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    buttons = []
    for device in coordinator.devices:
        device_group = device.device_group
        button_keys_for_group = BUTTON_GROUPS.get(device_group, [])

        for description in BUTTON_DESCRIPTIONS:
            if description.key in button_keys_for_group:
                buttons.append(EheimButton(coordinator, description, device))

    async_add_entities(buttons, True)


class EheimButton(CoordinatorEntity[EheimDigitalDataUpdateCoordinator], ButtonEntity):
    """Define an Eheim Button Entity."""

    _attr_has_entity_name = True
    entity_description: EheimButtonDescription

    def __init__(
        self,
        coordinator: EheimDigitalDataUpdateCoordinator,
        description: EheimButtonDescription,
        device: EheimDevice,
    ) -> None:
        """Initialize the Button."""
        super().__init__(coordinator)
        self.entity_description = description
        self._button_data = coordinator.data[device.mac]
        self._device = device
        LOGGER.debug(
            "Initializing Eheim Button for Device: %s Entity: %s",
            self._device.mac,
            self.entity_description.key,
        )

    async def async_press(self) -> None:
        """Handle the button press."""
        try:
            await self.entity_description.manual_feed_fn(self._device, self.coordinator)
        except EheimDigitalError as error:
            LOGGER.error(
                "Failed to press button for device %s: %s", self._device.mac, error
            )

    @property
    def unique_id(self) -> str:
        """Return the unique ID for this button."""
        return f"{self._device.model.lower().replace(' ', '_')}_{format_mac(self._device.mac).replace(':','_')}_{self.entity_description.key}"

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        LOGGER.debug("Eheim Button: Handling Coordinator Update")
        self._button_data = self.coordinator.data[self._device.mac]
        self.async_write_ha_state()

    @property
    def device_info(self):
        """Return device information."""
        return {
            "identifiers": {(DOMAIN, self._device.mac)},
            "name": self._device.name,
            "manufacturer": "Eheim",
            "model": self._device.model,
        }
