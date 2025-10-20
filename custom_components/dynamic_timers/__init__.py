"""Dynamic Timers Integration for Home Assistant."""
import logging
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.const import Platform
from homeassistant.helpers import discovery

from .const import DOMAIN
from .timer_manager import TimerManager

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SENSOR, Platform.BINARY_SENSOR]


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the Dynamic Timers component."""
    hass.data.setdefault(DOMAIN, {})

    # Initialize the timer manager
    manager = TimerManager(hass)
    hass.data[DOMAIN]["manager"] = manager

    # Load persisted timers
    await manager.async_load()

    # Register services
    await _async_register_services(hass, manager)

    # Set up platforms
    hass.async_create_task(
        discovery.async_load_platform(hass, Platform.SENSOR, DOMAIN, {}, config)
    )
    hass.async_create_task(
        discovery.async_load_platform(hass, Platform.BINARY_SENSOR, DOMAIN, {}, config)
    )

    _LOGGER.info("Dynamic Timers integration initialized")

    return True


async def _async_register_services(hass: HomeAssistant, manager: TimerManager) -> None:
    """Register all dynamic timer services."""

    async def handle_create(call):
        """Handle the create timer service call."""
        await manager.create_timer(
            name=call.data.get("name"),
            duration=call.data["duration"],
            actions=call.data["actions"],
            restart_behavior=call.data.get("restart_behavior", "resume"),
            groups=call.data.get("groups", [])
        )

    async def handle_pause(call):
        """Handle the pause timer service call."""
        name = call.data.get("name")
        group = call.data.get("group")

        if name:
            await manager.pause_timer(name)
        elif group:
            await manager.pause_group(group)

    async def handle_resume(call):
        """Handle the resume timer service call."""
        name = call.data.get("name")
        group = call.data.get("group")

        if name:
            await manager.resume_timer(name)
        elif group:
            await manager.resume_group(group)

    async def handle_cancel(call):
        """Handle the cancel timer service call."""
        name = call.data.get("name")
        group = call.data.get("group")

        if name:
            await manager.cancel_timer(name)
        elif group:
            await manager.cancel_group(group)

    async def handle_extend(call):
        """Handle the extend timer service call."""
        name = call.data.get("name")
        group = call.data.get("group")
        add_duration = call.data.get("add_duration")
        new_expiry = call.data.get("new_expiry")

        if name:
            await manager.extend_timer(name, add_duration, new_expiry)
        elif group:
            await manager.extend_group(group, add_duration, new_expiry)

    # Register services
    hass.services.async_register(DOMAIN, "create", handle_create)
    hass.services.async_register(DOMAIN, "pause", handle_pause)
    hass.services.async_register(DOMAIN, "resume", handle_resume)
    hass.services.async_register(DOMAIN, "cancel", handle_cancel)
    hass.services.async_register(DOMAIN, "extend", handle_extend)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    # Stop the timer manager
    if DOMAIN in hass.data:
        manager = hass.data[DOMAIN].get("manager")
        if manager:
            await manager.async_stop()

    return True
