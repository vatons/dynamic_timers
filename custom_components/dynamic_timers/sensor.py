"""Sensor platform for Dynamic Timers."""
import logging

from homeassistant.components.sensor import SensorEntity
from homeassistant.core import HomeAssistant, callback, Event
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.event import async_track_time_interval
from datetime import timedelta

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType = None,
) -> None:
    """Set up the Dynamic Timers sensor platform."""
    manager = hass.data[DOMAIN]["manager"]
    async_add_entities([DynamicTimersSensor(hass, manager)], True)


class DynamicTimersSensor(SensorEntity):
    """Sensor entity showing all active timers."""

    def __init__(self, hass: HomeAssistant, manager) -> None:
        """Initialize the sensor."""
        self.hass = hass
        self._manager = manager
        self._attr_name = "Dynamic Timers"
        self._attr_unique_id = f"{DOMAIN}_active_timers"
        self._attr_icon = "mdi:timer-outline"
        self._attr_should_poll = False
        self._unsub_update = None

    async def async_added_to_hass(self) -> None:
        """Register callbacks when entity is added."""
        # Listen for update events from the manager
        @callback
        def handle_update_event(event: Event) -> None:
            """Handle update event from timer manager."""
            self.async_schedule_update_ha_state()

        self._unsub_update = self.hass.bus.async_listen(
            f"{DOMAIN}_update", handle_update_event
        )

        # Also update periodically to keep in sync
        self._unsub_interval = async_track_time_interval(
            self.hass,
            lambda _: self.async_schedule_update_ha_state(),
            timedelta(seconds=1),
        )

    async def async_will_remove_from_hass(self) -> None:
        """Cleanup when entity is removed."""
        if self._unsub_update:
            self._unsub_update()
        if hasattr(self, '_unsub_interval') and self._unsub_interval:
            self._unsub_interval()

    @property
    def state(self):
        """Return the state of the sensor."""
        return len(self._manager.active_timers)

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        return {
            "timers": self._manager.active_timers,
        }
