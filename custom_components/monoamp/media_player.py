from asyncio.exceptions import CancelledError
import logging
from typing import Optional
from attr import dataclass

import voluptuous as vol

from homeassistant.helpers.typing import StateType
from homeassistant.components.media_player import MediaPlayerEntity, is_on
from homeassistant.components.number import NumberEntity
from homeassistant.helpers import entity_platform, config_validation as cv
from homeassistant.components.media_player.const import (
    MEDIA_TYPE_MUSIC,
    SUPPORT_NEXT_TRACK,
    SUPPORT_TURN_OFF,
    SUPPORT_TURN_ON,
    SUPPORT_VOLUME_MUTE,
    SUPPORT_SELECT_SOURCE,
    SUPPORT_VOLUME_SET,
    SUPPORT_VOLUME_STEP,
    SUPPORT_PAUSE,
    SUPPORT_PLAY,
    SUPPORT_NEXT_TRACK,
)

from homeassistant.const import (
    STATE_OFF,
    STATE_ON,
    STATE_PAUSED,
    STATE_PLAYING,
)

from . import MonoAmpEntity
from .const import DOMAIN, MAX_VOLUME_LIMIT

import websocket
import json
import asyncio
import datetime as dt

_LOGGER = logging.getLogger(__name__)

SUPPORT_MONOAMP = (
    SUPPORT_TURN_ON
    | SUPPORT_TURN_OFF
    | SUPPORT_VOLUME_MUTE
    | SUPPORT_SELECT_SOURCE
    | SUPPORT_VOLUME_SET
    | SUPPORT_VOLUME_STEP
)

SUPPORT_PANDORA = (
    SUPPORT_PLAY | SUPPORT_PAUSE | SUPPORT_NEXT_TRACK | SUPPORT_SELECT_SOURCE
)

SERVICE_SET_ZONE = "set_zone"


PANDORA_ROOMS = ["pianod", "pandora2"]


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

    entities = []
    entities.append(PandoraZone(coordinator, 1))
    entities.append(PandoraZone(coordinator, 2))

    async_add_entities(entities, True)

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


class PandoraZone(MediaPlayerEntity):
    def __init__(self, coordinator, index) -> None:
        super().__init__()
        self.coordinator = coordinator
        self.index = index
        self._room = PANDORA_ROOMS[index - 1]
        self._last_updated = dt.datetime.now()

    @property
    def supported_features(self) -> int:
        return SUPPORT_PANDORA

    @property
    def name(self) -> str:
        return f"Pandora {self.index}"

    @property
    def media_content_type(self) -> str:
        return MEDIA_TYPE_MUSIC

    @property
    def unique_id(self) -> str:
        return f"{super().unique_id} - Pandora {self.index}"

    async def async_update(self):
        url = "ws://192.168.2.128:4446/pianod/?protocol=json"
        thesocket = websocket.WebSocket()

        thesocket.connect(url)

        self._initial_data = json.loads(await self.recv_till_end(thesocket))
        # self._initial_data = self._initial_data

        thesocket.send("PLAYLIST LIST")

        self._playlist_list = json.loads(await self.recv_till_end(thesocket))

        # await thesocket.send("ROOM LIST")

        # room_list = json.loads(await self.recv_till_end(thesocket))

        # room_data = []
        # for room in room_list["data"]:
        thesocket.send(f"ROOM ENTER {PANDORA_ROOMS[self.index - 1]}")
        self._room_data = json.loads(await self.recv_till_end(thesocket))

        # room_data.append(tmp)

        # self._room_data = room_data

        thesocket.close()

        # ret = json.loads(ret)

        # ret["data"][0]

        self._last_updated = dt.datetime.now()
        pass

    async def recv_till_end(self, thesocket: websocket.WebSocket):
        return thesocket.recv()

    @property
    def source_list(self) -> list[str]:
        playlist_list = []
        for it in self._playlist_list["data"]:
            playlist_list.append(it["name"])

        return playlist_list

    @property
    def source(self):
        if "state" in self._room_data:
            return self._room_data["state"]["selectedPlaylist"]["name"]
        else:
            return ""

    @property
    def state(self) -> str:
        playback_state = self._room_data["state"]["playbackState"]

        if playback_state == "playing":
            return STATE_PLAYING
        else:
            return STATE_PAUSED

    @property
    def media_image_url(self) -> str:
        if self.song is not None:
            return self.song["albumArtUrl"]

    @property
    def media_artist(self) -> str:
        if self.song is not None:
            return self.song["artistName"]

    @property
    def media_album_name(self) -> str:
        if self.song is not None:
            return self.song["albumName"]

    @property
    def media_title(self) -> str:
        if self.song is not None:
            return self.song["name"]

    @property
    def media_duration(self) -> int:
        if self.song is not None:
            return int(self.song["duration"])

    @property
    def media_position(self) -> int:
        if self.song is not None:
            return int(self.song["timeIndex"])

    @property
    def media_position_updated_at(self) -> dt.datetime:
        return self._last_updated

    @property
    def song(self):
        if "currentSong" in self._room_data:
            return self._room_data["currentSong"]
        else:
            return None

    async def async_select_source(self, source):
        await self.media_command("STOP NOW")
        await self.media_command(f'select playlist name "{source}"')
        await self.media_command("PLAY")

    async def async_media_play(self):
        await self.media_command("PLAY")

    async def async_media_pause(self):
        await self.media_command("PAUSE")

    async def async_media_next_track(self):
        await self.media_command("SKIP")

    async def media_command(self, command):
        url = "ws://192.168.2.128:4446/pianod/?protocol=json"
        thesocket = websocket.WebSocket()

        thesocket.connect(url)
        thesocket.send(f"ROOM ENTER {PANDORA_ROOMS[self.index - 1]}")
        thesocket.send(f"{command}")
        thesocket.close()


class MonoAmpZone(MonoAmpEntity, MediaPlayerEntity):
    def __init__(self, coordinator, data_key, enabled):
        super().__init__(coordinator, data_key, enabled=enabled)

        self._receiver_max_volume = 38  #
        self._max_volume = MAX_VOLUME_LIMIT  # Percentage of max volume to allow

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

    async def async_volume_up(self):
        """Send volume up command."""
        await self.hass.async_add_executor_job(
            self.gateway.api_request,
            "ValueUp",
            {"Channel": self.channel, "Property": "VO"},
        )

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
