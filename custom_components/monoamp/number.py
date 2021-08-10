import logging

from homeassistant.components.number import NumberEntity
from homeassistant.helpers import entity_platform, config_validation as cv
from homeassistant.components.media_player.const import (
    MEDIA_TYPE_MUSIC,
    SUPPORT_TURN_OFF,
    SUPPORT_TURN_ON,
    SUPPORT_VOLUME_MUTE,
    SUPPORT_SELECT_SOURCE,
    SUPPORT_VOLUME_SET,
    SUPPORT_VOLUME_STEP,
)

from homeassistant.const import (
    STATE_OFF,
    STATE_ON,
)

from . import MonoAmpEntity
from .const import DOMAIN, MAX_VOLUME_LIMIT

_LOGGER = logging.getLogger(__name__)

PROP_MAP = {"VO": "volume", "BL": "balance", "BS": "bass", "TR": "treble"}
PROP_MAP_INV = {v: k for k, v in PROP_MAP.items()}

PROP_MAX = {"VO": int(38 * (MAX_VOLUME_LIMIT / 100)), "BL": 20, "BS": 14, "TR": 14}


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
    def __init__(self, coordinator, data_key, enabled, property_name):
        super().__init__(coordinator, data_key, enabled=enabled)
        self._attr_min_value = 0
        self._attr_max_value = PROP_MAX[PROP_MAP_INV[property_name]]
        self._attr_step = 1
        self.property_name = property_name

    @property
    def channel(self):
        return int(self.circuit["ZN"]) - 11

    @property
    def circuit(self):
        for kp in self.coordinator.data["Keypads"]:
            if kp["ZN"] == self._data_key:
                return kp

    async def async_set_value(self, value: float) -> None:
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

    @property
    def name(self) -> str:
        return f"{self.circuit['Name']} {self.property_name.capitalize()}"

    @property
    def unique_id(self):
        return f"{super().unique_id}_zone_{self.property_name}"

    @property
    def value(self) -> float:
        return self.circuit[PROP_MAP_INV[self.property_name]]

    @property
    def available(self) -> bool:
        return self.circuit["PR"] == 1
