""" This module Manages the properties of a Zone """

import logging

from homeassistant.components.number import NumberEntity

from . import MonoAmpEntity
from .const import DOMAIN, PROP_MAP_INV, PROP_MAX

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up entry."""
    entities = []
    coordinator = hass.data[DOMAIN][config_entry.entry_id]["coordinator"]

    for keypad in coordinator.data["Keypads"]:
        if keypad["Name"] != "None":
            for prop in PROP_MAP_INV:
                entities.append(MonoAmpZoneValue(coordinator, keypad["ZN"], True, prop))

    async_add_entities(entities)


class MonoAmpZoneValue(MonoAmpEntity, NumberEntity):
    """Represents the Value of Zone Property"""
    def __init__(self, coordinator, data_key, enabled, property_name):
        super().__init__(coordinator, data_key, enabled=enabled)
        self._attr_native_min_value = 0
        self._attr_native_max_value = PROP_MAX[PROP_MAP_INV[property_name]]
        self._attr_native_step = 1
        self.property_name = property_name

    @property
    def channel(self):
        """ Returns the channel mapped from the zone """
        return int(self.zone["ZN"]) - 11 if self.data_valid else 0

    @property
    def zone(self):
        """ Returns the zone corresponding to the object """
        if (
            self.coordinator.data is None
            or len(self.coordinator.data) == 0
            or len(self.coordinator.data["Keypads"]) == 0
        ):
            return None

        kp = [
            kp for kp in self.coordinator.data["Keypads"] if kp["ZN"] == self._data_key
        ]
        return kp[0] if len(kp) > 0 else None

    async def async_set_native_value(self, value: float) -> None:
        _LOGGER.info("MonoAmpoZoneValue: Set %s", self.property_name)
        await self.hass.async_add_executor_job(
            self.gateway.api_request,
            "Value",
            {
                "Channel": self.channel,
                "Property": PROP_MAP_INV[self.property_name],
                "Value": int(value),
            },
        )

    def set_native_value(self, value: float) -> None:
        return self.async_set_native_value(value)

    @property
    def name(self) -> str:
        return (
            f"{self.zone['Name']} {self.property_name.capitalize()}"
            if self.data_valid
            else f"----- {self.property_name.capitalize()}"
        )

    @property
    def unique_id(self):
        return f"{super().unique_id}_zone_{self.property_name}"

    @property
    def native_value(self) -> float:
        return self.zone[PROP_MAP_INV[self.property_name]] if self.data_valid else 0

    @property
    def available(self) -> bool:
        return self.zone["PR"] == 1 if self.data_valid else False

    @property
    def data_valid(self):
        """ Returns True is data is valid """
        return True if self.zone is not None else False
