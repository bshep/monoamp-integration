""" The media_player implementation """

import json
import datetime as dt
import logging
import websocket

import voluptuous as vol
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import StateType
from homeassistant.components.media_player import (
    MediaPlayerEntity, BrowseMedia)
from homeassistant.helpers import entity_platform, config_validation as cv
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
)

from homeassistant.components.media_player.const import (
    MediaPlayerEntityFeature, MediaPlayerState, MediaType
)


from . import MonoAmpEntity
from .const import DOMAIN, MAX_VOLUME_LIMIT



_LOGGER = logging.getLogger(__name__)

SUPPORT_MONOAMP = (
    MediaPlayerEntityFeature.TURN_ON
    | MediaPlayerEntityFeature.TURN_OFF
    | MediaPlayerEntityFeature.VOLUME_MUTE
    | MediaPlayerEntityFeature.SELECT_SOURCE
    | MediaPlayerEntityFeature.VOLUME_SET
    | MediaPlayerEntityFeature.VOLUME_STEP
)

SUPPORT_PANDORA = (
    MediaPlayerEntityFeature.PLAY
    | MediaPlayerEntityFeature.PAUSE
    | MediaPlayerEntityFeature.NEXT_TRACK
    | MediaPlayerEntityFeature.SELECT_SOURCE
)

SERVICE_SET_ZONE = "set_zone"


async def async_setup_entry(hass: HomeAssistant, config_entry, async_add_entities):
    """Setup Mono-Amp Entries"""
    entities = []
    coordinator: DataUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id][
        "coordinator"
    ]

    for keypad in coordinator.data["Keypads"]:
        if keypad["Name"] != "None":
            entities.append(MonoAmpZone(coordinator, keypad["ZN"], True))
    #     enabled = zone["name"] not in GENERIC_CIRCUIT_NAMES
    #     entities.append(MonoAmpSwitch(coordinator, zone_num, enabled))

    async_add_entities(entities)

    # Setup Pandora Entries
    entities = []

    room_list = await get_room_list(hass, config_entry)

    for i in range(len(room_list)):
        entities.append(PandoraZone(hass, config_entry, room_list, i + 1))

    async_add_entities(entities, True)

    # Setup Services to set zones
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


async def get_room_list(hass: HomeAssistant, config_entry) -> list:
    """ Returns room list from pandora """
    url = f"ws://{config_entry.data['host']}:4446/pianod/?protocol=json"
    tmp_socket:websocket.WebSocket = websocket.WebSocket()

    await hass.async_add_executor_job(tmp_socket.connect, url)

    await hass.async_add_executor_job(tmp_socket.send, "ROOM LIST")
    valid_data = False

    while not valid_data:
        socket_data = await hass.async_add_executor_job(tmp_socket.recv)

        json_data = json.loads(socket_data)
        if "code" in json_data:
            if json_data["code"] == 203:
                valid_data = True

    await hass.async_add_executor_job(tmp_socket.close)

    ret = [item["room"] for item in json_data["data"]]
    ret.reverse()
    return ret


class PandoraZone(MediaPlayerEntity):
    """ Represents a Zone """
    def __init__(self, hass: HomeAssistant, config_entry, room_list, index) -> None:
        super().__init__()
        self.hass: HomeAssistant = hass
        self.index: int = index
        self._room_list: list = room_list
        self._room: str = self._room_list[index - 1]
        self._room_data: str = ""
        self._last_updated: str = dt.datetime.now()
        self._the_socket: websocket.WebSocket = None
        self._url: str = f"ws://{config_entry.data['host']}:4446/pianod/?protocol=json"
        self._playlist_list: str = ""

    @property
    def supported_features(self) -> int:
        return SUPPORT_PANDORA

    @property
    def name(self) -> str:
        return f"Pandora {self.index}"

    @property
    def media_content_type(self) -> str:
        return MediaType.MUSIC

    @property
    def unique_id(self) -> str:
        return f"{super().unique_id} - Pandora {self.index}"

    async def async_browse_media(self, media_content_type: str | None = None,
                                    media_content_id: str | None = None) -> BrowseMedia:
        """ Unimplemented method """
        return None

    def clear_playlist(self) -> None:
        """ Unimplemented method """

    async def async_update(self):
        """ Updates the current state of the zone """
        the_socket = await self.get_socket()

        try:
            await self.hass.async_add_executor_job(the_socket.send, "PLAYLIST LIST")

            self._playlist_list = await self.recv_data(203)

            await self.hass.async_add_executor_job(
                the_socket.send, f"ROOM ENTER {self._room_list[self.index - 1]}"
            )
            self._room_data = await self.recv_data(200)
        except BrokenPipeError:
            await self.hass.async_add_executor_job(self.socket_connect)

        self._last_updated = dt.datetime.now()

    async def recv_data(self, valid_code):
        """ Get data from pandora """
        the_socket = await self.get_socket()
        valid_data = False

        while not valid_data:
            socket_data = await self.hass.async_add_executor_job(the_socket.recv)

            json_data = json.loads(socket_data)
            if "code" in json_data:
                if json_data["code"] == valid_code:
                    valid_data = True

        return json_data

    async def get_socket(self) -> websocket.WebSocket:
        """ returns the associated socket """
        if self._the_socket is None:
            self._the_socket = await self.socket_connect()
        if self._the_socket.connected is False:
            self._the_socket = await self.socket_connect()

        return self._the_socket

    async def socket_connect(self) -> websocket.WebSocket:
        """ connect the socket """
        self._the_socket = websocket.WebSocket()

        await self.hass.async_add_executor_job(self._the_socket.connect, self._url)
        return self._the_socket

    @property
    def source_list(self) -> list[str]:
        return [item["name"] for item in self._playlist_list["data"]]

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
            return MediaPlayerState.PLAYING
        else:
            return MediaPlayerState.PAUSED

    @property
    def media_image_url(self) -> str:
        if self.song is not None:
            return self.song["albumArtUrl"]
        else:
            return ""

    @property
    def media_artist(self) -> str:
        if self.song is not None:
            return self.song["artistName"]
        else:
            return ""

    @property
    def media_album_name(self) -> str:
        if self.song is not None:
            return self.song["albumName"]
        else:
            return ""

    @property
    def media_title(self) -> str:
        if self.song is not None:
            return self.song["name"]
        else:
            return ""

    @property
    def media_duration(self) -> int:
        if self.song is not None:
            if self.song["duration"] is not None:
                try:
                    return int(self.song["duration"])
                except TypeError:
                    return 0
            else:
                return 0
        else:
            return 0

    @property
    def media_position(self) -> int:
        if self.song is not None:
            if self.song["timeIndex"] is not None:
                try:
                    return int(self.song["timeIndex"])
                except TypeError:
                    return 0
            else:
                return 0
        else:
            return 0

    @property
    def media_position_updated_at(self) -> dt.datetime:
        return self._last_updated

    @property
    def song(self) -> list:
        """ return the cuurent song """
        if "currentSong" in self._room_data:
            return self._room_data["currentSong"]

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
        """ send a media command """
        the_socket: websocket.WebSocket = await self.get_socket()

        if the_socket.connected is False:
            await self.socket_connect()

        if the_socket.connected is False:
            _LOGGER.error("Could not connect websocket")
            return
            
        try:

            await self.hass.async_add_executor_job(
                the_socket.send, f"ROOM ENTER {self._room_list[self.index - 1]}"
            )
            await self.hass.async_add_executor_job(the_socket.send, f"{command}")
        except BrokenPipeError:
            _LOGGER.error("Socket was disconnected, will try to reconnect")





class MonoAmpZone(MonoAmpEntity, MediaPlayerEntity):
    """ Class that defines a MonoAmp Zone """
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
        """ Sets the properties of a zone """
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
        return self.zone["MU"] == 1 if self.data_valid else False

    @property
    def source(self):
        """Return the current input source of the device."""
        return (
            self.coordinator.data["Sources"][self.zone["CH"] - 1]
            if self.data_valid
            else ""
        )

    @property
    def source_list(self):
        """List of available input sources."""
        # return list(filter(lambda i: "None" not in i, self.coordinator.data["Sources"]))
        return (
            [item for item in self.coordinator.data["Sources"] if "None" not in item]
            if self.data_valid
            else []
        )

    @property
    def name(self):
        return f"{self.zone['Name']} Zone" if self.data_valid else "--- Zone"

    @property
    def volume_level(self) -> float:
        return float(self.zone["VO"] / (38 * 0.8)) if self.data_valid else 0

    @property
    def state(self) -> StateType:
        return MediaPlayerState.ON if self.data_valid and self.zone["PR"] == 1 else MediaPlayerState.OFF

    @property
    def supported_features(self) -> int:
        return SUPPORT_MONOAMP

    @property
    def media_content_type(self):
        """Return the content type of current playing media."""
        return MediaType.MUSIC

    @property
    def channel(self):
        """ Returns the channel, mapped from zone on MonoAmp """
        return int(self.zone["ZN"]) - 11 if self.data_valid else 0

    @property
    def zone(self):
        """ Returns the keypad from the zone data """
        if (
            self.coordinator.data is None
            or len(self.coordinator.data) == 0
            or len(self.coordinator.data["Keypads"]) == 0
        ):
            return None

        try:
            kp = [
                kp
                for kp in self.coordinator.data["Keypads"]
                if kp["ZN"] == self._data_key
            ]
            return kp[0] if len(kp) > 0 else None
        except Exception:
            return None

    @property
    def is_on(self) -> bool:
        """ Returns True if zone is on """
        return self.zone["PR"] == 1 if self.data_valid else False

    @property
    def data_valid(self):
        """ Returns True if data is valid """
        return True if self.zone is not None else False

    async def async_select_source(self, source):
        """Set the input source."""
        for i, value in enumerate(self.source_list):
            if source == value:
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

    async def _async_set_power(self, zone_value) -> None:

        await self.hass.async_add_executor_job(
            self.gateway.api_request,
            "Value",
            {
                "Channel": self.channel,
                "Property": "PR",
                "Value": zone_value,
            },
        )
