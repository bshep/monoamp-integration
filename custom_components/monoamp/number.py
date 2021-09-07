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
    def __init__(self, coordinator, data_key, enabled, property_name):
        super().__init__(coordinator, data_key, enabled=enabled)
        self._attr_min_value = 0
        self._attr_max_value = PROP_MAX[PROP_MAP_INV[property_name]]
        self._attr_step = 1
        self.property_name = property_name

    @property
    def channel(self):
        return int(self.zone["ZN"]) - 11 if self.data_valid else 0

    @property
    def zone(self):
        if (
            self.coordinator.data == None
            or len(self.coordinator.data) == 0
            or len(self.coordinator.data["Keypads"]) == 0
        ):
            return None

        kp = [
            kp for kp in self.coordinator.data["Keypads"] if kp["ZN"] == self._data_key
        ]
        return kp[0] if len(kp) > 0 else None

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
        return (
            f"{self.zone['Name']} {self.property_name.capitalize()}"
            if self.data_valid
            else f"----- {self.property_name.capitalize()}"
        )

    @property
    def unique_id(self):
        return f"{super().unique_id}_zone_{self.property_name}"

    @property
    def value(self) -> float:
        return self.zone[PROP_MAP_INV[self.property_name]] if self.data_valid else 0

    @property
    def available(self) -> bool:
        return self.zone["PR"] == 1 if self.data_valid else False

    @property
    def data_valid(self):
        return True if self.zone is not None else False
