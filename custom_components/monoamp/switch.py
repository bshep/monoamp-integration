"""Support for a MonoAmp 'circuit' switch."""
import logging

# from screenlogicpy.const import DATA as SL_DATA, GENERIC_CIRCUIT_NAMES, ON_OFF

from homeassistant.components.switch import SwitchEntity

from . import MonoAmpEntity
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up entry."""
    entities = []
    coordinator = hass.data[DOMAIN][config_entry.entry_id]["coordinator"]

    for keypad in coordinator.data["Keypads"]:
        if keypad["Name"] != "None":
            entities.append(MonoAmpSwitch(coordinator, keypad["ZN"], True))
    #     enabled = circuit["name"] not in GENERIC_CIRCUIT_NAMES
    #     entities.append(MonoAmpSwitch(coordinator, circuit_num, enabled))

    async_add_entities(entities)


class MonoAmpSwitch(MonoAmpEntity, SwitchEntity):
    """MonoAmp switch entity."""

    @property
    def name(self):
        """Get the name of the switch."""
        # return f"{self.gateway_name} {self.circuit['name']}"
        kp = self.circuit
        if kp is not None:
            return f"{self.circuit['Name']}"
        else:
            return "None"

    @property
    def channel(self):
        return int(self.circuit["ZN"]) - 11

    @property
    def source(self):
        return int(self.circuit["CH"])

    @property
    def is_on(self) -> bool:
        """Get whether the switch is in on state."""
        return self.circuit["PR"] == 1

    async def async_turn_on(self, **kwargs) -> None:
        """Send the ON command."""
        return await self._async_set_circuit("1")
        # return await self._async_set_circuit(ON_OFF.ON)

    async def async_turn_off(self, **kwargs) -> None:
        """Send the OFF command."""
        return await self._async_set_circuit("0")
        # return False

    async def _async_set_circuit(self, circuit_value) -> None:

        ret = await self.hass.async_add_executor_job(
            self.gateway.api_request,
            "Value",
            {
                "Channel": self.channel,
                "Property": "PR",
                "Value": circuit_value,
            },
        )

        _LOGGER.info("MonoAmpSwitch: %s", ret)

    @property
    def circuit(self):
        for kp in self.coordinator.data["Keypads"]:
            if kp["ZN"] == self._data_key:
                return kp
