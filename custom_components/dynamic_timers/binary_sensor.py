"""Binary sensor platform for Dynamic Timers."""
import logging

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType = None,
) -> None:
    """Set up the Dynamic Timers binary sensor platform."""
    manager = hass.data[DOMAIN]["manager"]
    async_add_entities([DynamicTimersReadySensor(hass, manager)], True)


class DynamicTimersReadySensor(BinarySensorEntity):
    """Binary sensor showing if the timer system is ready."""

    def __init__(self, hass: HomeAssistant, manager) -> None:
        """Initialize the binary sensor."""
        self.hass = hass
        self._manager = manager
        self._attr_name = "Dynamic Timers Ready"
        self._attr_unique_id = f"{DOMAIN}_ready"
        self._attr_icon = "mdi:check-circle"
        self._attr_device_class = None

    @property
    def is_on(self):
        """Return true if the timer system is ready."""
        return self._manager.ready

    @property
    def should_poll(self):
        """Enable polling for this sensor."""
        return True

    async def async_update(self):
        """Update the sensor state."""
        # The manager updates itself, we just need to refresh
        pass
