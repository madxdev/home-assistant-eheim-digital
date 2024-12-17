"""Platform for Switch integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.switch import (
    SwitchDeviceClass,
    SwitchEntity,
    SwitchEntityDescription,
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
class EheimSwitchDescriptionMixin:
    """Mixin for Eheim switch."""

    set_state_fn: Callable[[EheimDevice, EheimDigitalDataUpdateCoordinator, bool], Any]
    state_key: str


@dataclass
class EheimSwitchDescription(SwitchEntityDescription, EheimSwitchDescriptionMixin):
    """Class describing Eheim switch entities."""

    attr_fn: Callable[[dict[str, Any]], dict[str, StateType]] = lambda _: {}


SWITCH_DESCRIPTIONS: tuple[EheimSwitchDescription, ...] = (
    EheimSwitchDescription(
        key="filter_is_active",
        name="Filter Pump",
        device_class=SwitchDeviceClass.SWITCH,
        entity_registry_enabled_default=True,
        state_key="filterActive",
        set_state_fn=lambda device,
        coordinator,
        state: coordinator.api_client.set_filter_state(device, state),
    ),
    EheimSwitchDescription(
        key="ph_control_is_active",
        name="PH Controler",
        device_class=SwitchDeviceClass.SWITCH,
        entity_registry_enabled_default=True,
        state_key="active",
        set_state_fn=lambda device,
        coordinator,
        state: coordinator.api_client.set_phcontrol_state(device, state),
    ),
)

SWITCH_SENSOR_GROUPS = {
    # Define binary sensor groups similar to SENSOR_GROUPS
    "ph_control": ["ph_control_is_active"],
    "filter": ["filter_is_active"],
}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Add EheimDevice entities from a config_entry."""
    LOGGER.debug("Setting up Eheim Digital Switch platform")

    coordinator: EheimDigitalDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    switches = []
    for device in coordinator.devices:
        device_group = device.device_group
        switch_keys_for_group = SWITCH_SENSOR_GROUPS.get(device_group, [])

        for description in SWITCH_DESCRIPTIONS:
            if description.key in switch_keys_for_group:
                switches.append(EheimSwitch(coordinator, description, device))

    async_add_entities(switches, True)


class EheimSwitch(CoordinatorEntity[EheimDigitalDataUpdateCoordinator], SwitchEntity):
    """Define an Eheim Switch Entity."""

    _attr_has_entity_name = True
    entity_description: EheimSwitchDescription

    def __init__(
        self,
        coordinator: EheimDigitalDataUpdateCoordinator,
        description: EheimSwitchDescription,
        device: EheimDevice,
    ) -> None:
        """Initialize the Switch."""
        super().__init__(coordinator)
        self.entity_description = description
        self._switch_data = coordinator.data[device.mac]
        self._device = device
        LOGGER.debug(
            "Initializing Eheim Switch for Device: %s Entity: %s",
            self._device.mac,
            self.entity_description.key,
        )

    @property
    def is_on(self) -> bool:
        """Return True if the switch is on."""
        return bool(self._switch_data.get(self.entity_description.state_key))

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        await self.entity_description.set_state_fn(self._device, self.coordinator, True)
        self._switch_data[self.entity_description.state_key] = 1
        self.async_write_ha_state()
        # await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        try:
            await self.entity_description.set_state_fn(
                self._device, self.coordinator, False
            )
            self._switch_data[self.entity_description.state_key] = 0
            self.async_write_ha_state()
            # await self.coordinator.async_request_refresh()
        except EheimDigitalError as error:
            LOGGER.error(
                "Failed to turn off switch for device %s: %s", self._device.mac, error
            )
            self._attr_available = False
            self.async_write_ha_state()

    @property
    def unique_id(self) -> str:
        """Return the unique ID for this switch."""
        return f"{self._device.model.lower().replace(' ', '_')}_{format_mac(self._device.mac).replace(':','_')}_{self.entity_description.key}"

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        LOGGER.debug("Eheim Switch: Handling Coordinator Update")
        self._switch_data = self.coordinator.data[self._device.mac]
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
