"""The Mono Amp (HTTP) Audio Amplifier integration."""
from __future__ import annotations
from typing import Sequence

from datetime import timedelta
import logging
import asyncio

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers import device_registry as dr
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

import requests
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["media_player", "number"]

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up House Audio Amplifier from a config entry."""
    # hass.data[DOMAIN][entry.entry_id] = MyApi(...)
    hass.data[DOMAIN] = {}
    api_lock = asyncio.Lock()

    gateway = MonoAmpGateway(entry.data["host"])

    coordinator = MonoAmpDataUpdateCoordinator(
        hass,
        config_entry=entry,
        gateway=gateway,
        api_lock=api_lock,
    )

    hass.data[DOMAIN][entry.entry_id] = {
        "coordinator": coordinator,
        "listener": entry.add_update_listener(async_update_listener),
    }

    await coordinator.async_config_entry_first_refresh()

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)
    return True


async def async_update_listener(hass: HomeAssistant, entry: ConfigEntry):
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""

    await hass.config_entries.async_forward_entry_unload(entry, "media_player")
    await hass.config_entries.async_forward_entry_unload(entry, "number")

    hass.data[DOMAIN].pop(entry.entry_id)

    return True


class MonoAmpDataUpdateCoordinator(DataUpdateCoordinator):
    """ The update coordinator for the MonoAmp integration """
    def __init__(self, hass, *, gateway, config_entry, api_lock):
        """Initialize the MonoAmp Data Update Coordinator."""
        self.config_entry = config_entry
        self.api_lock = api_lock
        self.gateway = gateway

        interval = timedelta(seconds=5)
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=interval,
        )

    async def _async_update_data(self):
        """Fetch data from the MonoAmp gateway."""
        try:
            async with self.api_lock:
                await self.hass.async_add_executor_job(self.gateway.update)
        except Exception as error:
            _LOGGER.warning("MonoAmpError: %s", error)

        return self.gateway.get_data()


class MonoAmpEntity(CoordinatorEntity):
    """Entity that represents a MonoAmp

    Args:
        CoordinatorEntity (CoordinatorEntity): object of type CoordinatorEntity from Home Assistant
    """
    def __init__(self, coordinator, data_key, enabled=True):
        """Initialize of the entity."""
        super().__init__(coordinator)
        self._data_key = data_key
        self._enabled_default = enabled

    def unload(self) -> bool:
        """Run when integration unloaded

        Returns:
            bool: always returns true
        """
        return True

    @property
    def entity_registry_enabled_default(self):
        """Entity enabled by default."""
        return self._enabled_default

    @property
    def mac(self):
        """Mac address."""
        return self.coordinator.config_entry.entry_id

    @property
    def unique_id(self):
        """Entity Unique ID."""
        return f"{self.mac}_{self._data_key}"

    @property
    def config_data(self):
        """Shortcut for config data."""
        return self.coordinator.data["config"]

    @property
    def gateway(self):
        """Return the gateway."""
        return self.coordinator.gateway

    @property
    def gateway_name(self):
        """Return the configured name of the gateway."""
        return self.gateway.name

    @property
    def device_info(self):
        """Return device information for the controller."""
        return {
            "connections": {(dr.CONNECTION_NETWORK_MAC, self.mac)},
            "name": self.gateway_name,
            "manufacturer": "MonoPrice",
            "model": "MA1000",
        }


class MonoAmpGateway:
    """ 
        class:  MonoAmpGateway
    """
    def __init__(self, host) -> None:
        self.host: str = host
        self.api_endpoint: str = "http://" + self.host + ":50230/api"
        self.amp_state: str = None

    def update(self) -> None:
        """Updates the state of the Class"""
        result_json = self.api_request("AmpState")

        if result_json != "":
            self.amp_state = result_json

            self.amp_state["Keypads"] = []
            for kp in range(0, self.amp_state["KeypadCount"]):
                self.amp_state["Keypads"].insert(
                    kp, self.api_request("keypad", args={"chan": kp})
                )

    def api_request(self, request_id, args=None) -> str:
        """Sends an API request to the MonoAmp Gateway

        Args:
            request_id (str): the request_id
            args (str, optional): Additional Arg to send. Defaults to None.

        Returns:
            str: the result of the request.
        """
        if args is None:
            args = {}

        ret = None

        try:
            ret = requests.get(
                self.api_endpoint + "/" + request_id, params=args, timeout=1
            )

            ret = ret.json()
        except Exception as ex:
            _LOGGER.error("MonoAmpGateway - api_request: %s", ex)
            ret = ""

        return ret

    def get_data(self) -> str:
        """Return the data in amp_state

        Returns:
            str: data
        """
        return self.amp_state

    @property
    def name(self) -> str:
        """Returns the name of the class

        Returns:
            str: the name
        """
        return "MonoAmp Gateway"
