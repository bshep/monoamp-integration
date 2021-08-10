import logging
from typing import Optional

import voluptuous as vol

from homeassistant.helpers.typing import StateType
from homeassistant.components.media_player import MediaPlayerEntity
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

SUPPORT_MONOAMP = (
    SUPPORT_TURN_ON
    | SUPPORT_TURN_OFF
    | SUPPORT_VOLUME_MUTE
    | SUPPORT_SELECT_SOURCE
    | SUPPORT_VOLUME_SET
    | SUPPORT_VOLUME_STEP
)

SERVICE_SET_ZONE = "set_zone"


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up entry."""
    entities = []
    coordinator = hass.data[DOMAIN][config_entry.entry_id]["coordinator"]

    for keypad in coordinator.data["Keypads"]:
        if keypad["Name"] != "None":
            entities.append(MonoAmpZone(coordinator, keypad["ZN"], True))
    #     enabled = circuit["name"] not in GENERIC_CIRCUIT_NAMES
    #     entities.append(MonoAmpSwitch(coordinator, circuit_num, enabled))

    async_add_entities(entities)

    platform = entity_platform.async_get_current_platform()

    platform.async_register_entity_service(
        SERVICE_SET_ZONE,
        {
            vol.Optional("treble_value"): cv.positive_int,
            vol.Optional("bass_value"): cv.positive_int,
            vol.Optional("balance_value"): cv.positive_int,
            vol.Optional("volume_value"): cv.positive_int,
            vol.Optional("mute_value"): cv.boolean,
        },
        "async_set_zone",
    )


class MonoAmpZone(MonoAmpEntity, MediaPlayerEntity):
    def __init__(self, coordinator, data_key, enabled):
        super().__init__(coordinator, data_key, enabled=enabled)

        self._receiver_max_volume = 38  #
        self._max_volume = MAX_VOLUME_LIMIT  # Percentage of max volume to allow

    async def async_volume_up(self):
        """Send volume up command."""
        await self.hass.async_add_executor_job(
            self.gateway.api_request,
            "ValueUp",
            {"Channel": self.channel, "Property": "VO"},
        )

    async def async_set_zone(
        self,
        treble_value=None,
        bass_value=None,
        balance_value=None,
        volume_value=None,
        mute_value=None,
    ):
        if treble_value is not None:
            await self.hass.async_add_executor_job(
                self.gateway.api_request,
                "Value",
                {"Channel": self.channel, "Property": "TR", "Value": treble_value},
            )

        if bass_value is not None:
            await self.hass.async_add_executor_job(
                self.gateway.api_request,
                "Value",
                {"Channel": self.channel, "Property": "BS", "Value": bass_value},
            )

        if balance_value is not None:
            await self.hass.async_add_executor_job(
                self.gateway.api_request,
                "Value",
                {"Channel": self.channel, "Property": "BL", "Value": balance_value},
            )

        if volume_value is not None:
            await self.async_set_volume_level(volume_value / 38)

        if mute_value is not None:
            await self.async_mute_volume(mute_value)

    async def async_volume_down(self):
        """Send volume up command."""
        await self.hass.async_add_executor_job(
            self.gateway.api_request,
            "ValueDn",
            {"Channel": self.channel, "Property": "VO"},
        )

    async def async_mute_volume(self, mute):
        """Send mute command."""
        if mute:
            mute_val = 1
        else:
            mute_val = 0

        await self.hass.async_add_executor_job(
            self.gateway.api_request,
            "Value",
            {"Channel": self.channel, "Property": "MU", "Value": mute_val},
        )

    async def async_set_volume_level(self, volume):
        """
        Set volume level, input is range 0..1.
        """
        target_vol = int(volume * (self._max_volume / 100) * self._receiver_max_volume)

        await self.hass.async_add_executor_job(
            self.gateway.api_request,
            "Value",
            {"Channel": self.channel, "Property": "VO", "Value": target_vol},
        )

    @property
    def is_volume_muted(self) -> bool:
        return self.circuit["MU"] == 1

    @property
    def source(self):
        """Return the current input source of the device."""
        return self.coordinator.data["Sources"][self.circuit["CH"] - 1]

    @property
    def source_list(self):
        """List of available input sources."""
        return list(filter(lambda i: "None" not in i, self.coordinator.data["Sources"]))

    @property
    def name(self):
        """Get the name of the switch."""
        # return f"{self.gateway_name} {self.circuit['name']}"
        if self.circuit is not None:
            return f"{self.circuit['Name']} Zone"
        else:
            return "None"

    @property
    def volume_level(self) -> float:
        return float(self.circuit["VO"] / (38 * 0.8))

    @property
    def state(self) -> StateType:
        if self.circuit["PR"] == 1:
            return STATE_ON
        else:
            return STATE_OFF

    @property
    def supported_features(self) -> int:
        return SUPPORT_MONOAMP

    @property
    def media_content_type(self):
        """Return the content type of current playing media."""
        return MEDIA_TYPE_MUSIC

    @property
    def channel(self):
        return int(self.circuit["ZN"]) - 11

    @property
    def circuit(self):
        for kp in self.coordinator.data["Keypads"]:
            if kp["ZN"] == self._data_key:
                return kp

    @property
    def is_on(self) -> bool:
        """Get whether the switch is in on state."""
        return self.circuit["PR"] == 1

    async def async_select_source(self, source):
        """Set the input source."""
        for i in range(0, len(self.source_list)):
            if source == self.source_list[i]:
                return await self.hass.async_add_executor_job(
                    self.gateway.api_request,
                    "Value",
                    {
                        "Channel": self.channel,
                        "Property": "CH",
                        "Value": i + 1,
                    },
                )

    async def async_turn_on(self, **kwargs) -> None:
        """Send the ON command."""
        return await self._async_set_power("1")

    async def async_turn_off(self, **kwargs) -> None:
        """Send the OFF command."""
        return await self._async_set_power("0")

    async def _async_set_power(self, circuit_value) -> None:

        await self.hass.async_add_executor_job(
            self.gateway.api_request,
            "Value",
            {
                "Channel": self.channel,
                "Property": "PR",
                "Value": circuit_value,
            },
        )
