"""Timer Manager for Dynamic Timers."""
import asyncio
import logging
import uuid
from datetime import datetime, timedelta
from typing import Any, Optional

from homeassistant.core import HomeAssistant
from homeassistant.helpers import template
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.storage import Store

from .const import (
    DOMAIN,
    STORAGE_KEY,
    STORAGE_VERSION,
    STATE_ACTIVE,
    STATE_PAUSED,
    RESTART_RESUME,
    RESTART_SKIP,
    RESTART_EXECUTE,
    ACTION_EVENT,
    ACTION_SERVICE,
    CHECK_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)


class TimerManager:
    """Manage dynamic timers."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the timer manager."""
        self.hass = hass
        self._timers: dict[str, dict[str, Any]] = {}
        self._store = Store(hass, STORAGE_VERSION, STORAGE_KEY)
        self._check_task = None
        self._ready = False

    @property
    def ready(self) -> bool:
        """Return if the manager is ready."""
        return self._ready

    @property
    def active_timers(self) -> dict[str, dict[str, Any]]:
        """Return all active timers."""
        return {
            name: self._get_timer_state(name, timer)
            for name, timer in self._timers.items()
        }

    def _get_timer_state(self, name: str, timer: dict[str, Any]) -> dict[str, Any]:
        """Get the current state of a timer."""
        state = {
            "name": name,
            "state": timer["state"],
            "groups": timer["groups"],
            "restart_behavior": timer["restart_behavior"],
            "actions": timer.get("actions", []),
        }

        if timer["state"] == STATE_ACTIVE and timer.get("expiry"):
            state["expiry"] = timer["expiry"]
        elif timer["state"] == STATE_PAUSED:
            state["paused_duration"] = timer.get("remaining_duration", 0)

        return state

    async def async_load(self) -> None:
        """Load timers from storage."""
        data = await self._store.async_load()

        if data is not None:
            self._timers = data.get("timers", {})
            _LOGGER.debug("Loaded %d timers from storage", len(self._timers))

            # Handle restart behavior
            await self._handle_restart_behavior()

        # Start the check loop
        self._check_task = async_track_time_interval(
            self.hass,
            self._async_check_timers,
            timedelta(seconds=CHECK_INTERVAL),
        )

        self._ready = True
        _LOGGER.info("Timer manager ready with %d active timers", len(self._timers))

    async def _handle_restart_behavior(self) -> None:
        """Handle timers based on their restart behavior."""
        timers_to_remove = []

        for name, timer in list(self._timers.items()):
            try:
                restart_behavior = timer.get("restart_behavior", RESTART_RESUME)

                if timer["state"] == STATE_ACTIVE and timer.get("expiry"):
                    # Validate expiry timestamp
                    try:
                        expiry = datetime.fromisoformat(timer["expiry"])
                    except (ValueError, TypeError) as e:
                        _LOGGER.error(
                            "Timer '%s' has invalid expiry timestamp '%s': %s. Removing timer.",
                            name, timer.get("expiry"), e
                        )
                        timers_to_remove.append(name)
                        continue

                    is_expired = expiry <= datetime.now()

                    if restart_behavior == RESTART_RESUME:
                        if is_expired:
                            # Timer expired while HA was down, execute it now
                            _LOGGER.info("Executing expired timer '%s' (resume behavior)", name)
                            await self._execute_timer_actions(timer)
                            timers_to_remove.append(name)
                        else:
                            # Timer still active, let it continue
                            _LOGGER.debug("Timer '%s' will continue, expires at %s", name, expiry)

                    elif restart_behavior == RESTART_EXECUTE:
                        # Always execute immediately regardless of expiry
                        _LOGGER.info("Executing timer '%s' due to restart behavior", name)
                        await self._execute_timer_actions(timer)
                        timers_to_remove.append(name)

                    elif restart_behavior == RESTART_SKIP:
                        if is_expired:
                            # Discard expired timer without executing
                            _LOGGER.info("Skipping expired timer '%s'", name)
                            timers_to_remove.append(name)
                        else:
                            # Timer still active, let it continue
                            _LOGGER.debug("Timer '%s' will continue", name)
                elif timer["state"] == STATE_PAUSED:
                    # Paused timers are kept as-is
                    _LOGGER.debug("Timer '%s' is paused, keeping", name)
                else:
                    # Invalid state, remove timer
                    _LOGGER.warning("Timer '%s' has invalid state '%s'. Removing timer.", name, timer.get("state"))
                    timers_to_remove.append(name)

            except Exception as e:
                # Catch any other errors with this timer and remove it
                _LOGGER.error("Error processing timer '%s' during restart: %s. Removing timer.", name, e)
                timers_to_remove.append(name)

        # Remove timers marked for removal
        for name in timers_to_remove:
            del self._timers[name]

        if timers_to_remove:
            await self._async_save()
            _LOGGER.info("Removed %d invalid/broken timer(s) during startup", len(timers_to_remove))

    async def async_stop(self) -> None:
        """Stop the timer manager."""
        if self._check_task:
            self._check_task()
            self._check_task = None

        await self._async_save()
        _LOGGER.info("Timer manager stopped")

    async def _async_save(self) -> None:
        """Save timers to storage."""
        await self._store.async_save({"timers": self._timers})

    async def _async_check_timers(self, now=None) -> None:
        """Check timers for expiration."""
        expired_timers = []
        invalid_timers = []

        for name, timer in list(self._timers.items()):
            try:
                if timer["state"] == STATE_ACTIVE and timer.get("expiry"):
                    # Validate expiry timestamp
                    try:
                        expiry = datetime.fromisoformat(timer["expiry"])
                    except (ValueError, TypeError) as e:
                        _LOGGER.error(
                            "Timer '%s' has invalid expiry timestamp '%s': %s. Removing timer.",
                            name, timer.get("expiry"), e
                        )
                        invalid_timers.append(name)
                        continue

                    if expiry <= datetime.now():
                        _LOGGER.info("Timer '%s' expired", name)
                        await self._execute_timer_actions(timer)
                        expired_timers.append(name)
            except Exception as e:
                _LOGGER.error("Error checking timer '%s': %s. Removing timer.", name, e)
                invalid_timers.append(name)

        # Remove expired and invalid timers
        all_timers_to_remove = expired_timers + invalid_timers
        for name in all_timers_to_remove:
            if name in self._timers:
                del self._timers[name]

        if all_timers_to_remove:
            await self._async_save()
            self._notify_sensor_update()
            if invalid_timers:
                _LOGGER.warning("Removed %d invalid timer(s)", len(invalid_timers))

    async def _execute_timer_actions(self, timer: dict[str, Any]) -> None:
        """Execute timer actions."""
        actions = timer.get("actions", [])

        for action in actions:
            try:
                # Support both modern 'action' field and legacy 'action_type' field
                action_type = action.get("action_type")

                # If no action_type, check for modern 'action' field (service call)
                # or 'event' field (event fire)
                if not action_type:
                    if "event" in action:
                        action_type = ACTION_EVENT
                    elif "action" in action or "service" in action:
                        action_type = ACTION_SERVICE
                    else:
                        _LOGGER.warning("Action missing both 'action_type' and 'action'/'event' fields: %s", action)
                        continue

                if action_type == ACTION_EVENT:
                    await self._execute_event_action(action)
                elif action_type == ACTION_SERVICE:
                    await self._execute_service_action(action)
                else:
                    _LOGGER.warning("Unknown action type: %s", action_type)

            except Exception as e:
                _LOGGER.error("Error executing action: %s", e)

    async def _execute_event_action(self, action: dict[str, Any]) -> None:
        """Execute an event action."""
        event = action.get("event")
        event_data = action.get("event_data", {})

        # Render templates at execution time
        event_data = self._render_templates(event_data)

        self.hass.bus.async_fire(event, event_data)
        _LOGGER.debug("Fired event '%s' with data: %s", event, event_data)

    async def _execute_service_action(self, action: dict[str, Any]) -> None:
        """Execute a service action."""
        # Support both modern 'action' field and legacy 'service' field
        service = action.get("action") or action.get("service")

        if not service:
            _LOGGER.error("Service action missing 'action' or 'service' field: %s", action)
            return

        service_data = action.get("data", {})
        target = action.get("target", {})

        # Render templates at execution time
        service_data = self._render_templates(service_data)
        target = self._render_templates(target)

        # Split service into domain and service name
        if "." in service:
            domain, service_name = service.split(".", 1)
        else:
            _LOGGER.error("Invalid service format: %s", service)
            return

        await self.hass.services.async_call(
            domain, service_name, service_data, target=target
        )
        _LOGGER.debug("Called service '%s' with data: %s", service, service_data)

    def _render_templates(self, data: Any) -> Any:
        """Recursively render templates in data."""
        if isinstance(data, dict):
            return {key: self._render_templates(value) for key, value in data.items()}
        elif isinstance(data, list):
            return [self._render_templates(item) for item in data]
        elif isinstance(data, str):
            try:
                tpl = template.Template(data, self.hass)
                return tpl.async_render()
            except Exception as e:
                _LOGGER.warning("Failed to render template '%s': %s", data, e)
                return data
        else:
            return data

    def _notify_sensor_update(self) -> None:
        """Notify sensors to update."""
        # Fire an event that sensors can listen to
        self.hass.bus.async_fire(f"{DOMAIN}_update")

    async def create_timer(
        self,
        name: Optional[str],
        duration: int,
        actions: list[dict[str, Any]] | dict[str, Any],
        restart_behavior: str = RESTART_RESUME,
        groups: list[str] = None,
    ) -> str:
        """Create a new timer."""
        if groups is None:
            groups = []

        # Convert single action dict to list
        if isinstance(actions, dict):
            actions = [actions]

        # Generate name if not provided
        if not name:
            name = str(uuid.uuid4())

        # Check if timer already exists
        if name in self._timers:
            _LOGGER.warning("Timer '%s' already exists, replacing", name)

        # Calculate expiry timestamp
        expiry = datetime.now() + timedelta(seconds=duration)

        self._timers[name] = {
            "state": STATE_ACTIVE,
            "expiry": expiry.isoformat(),
            "actions": actions,
            "restart_behavior": restart_behavior,
            "groups": groups,
        }

        await self._async_save()
        self._notify_sensor_update()

        _LOGGER.info("Created timer '%s' with duration %d seconds", name, duration)
        return name

    async def pause_timer(self, name: str) -> None:
        """Pause a timer."""
        if name not in self._timers:
            _LOGGER.warning("Timer '%s' not found", name)
            return

        timer = self._timers[name]

        if timer["state"] != STATE_ACTIVE:
            _LOGGER.warning("Timer '%s' is not active", name)
            return

        # Calculate remaining duration
        expiry = datetime.fromisoformat(timer["expiry"])
        remaining = (expiry - datetime.now()).total_seconds()

        timer["state"] = STATE_PAUSED
        timer["remaining_duration"] = max(0, remaining)
        del timer["expiry"]

        await self._async_save()
        self._notify_sensor_update()

        _LOGGER.info("Paused timer '%s'", name)

    async def resume_timer(self, name: str) -> None:
        """Resume a paused timer."""
        if name not in self._timers:
            _LOGGER.warning("Timer '%s' not found", name)
            return

        timer = self._timers[name]

        if timer["state"] != STATE_PAUSED:
            _LOGGER.warning("Timer '%s' is not paused", name)
            return

        # Calculate new expiry from remaining duration
        remaining = timer.get("remaining_duration", 0)
        expiry = datetime.now() + timedelta(seconds=remaining)

        timer["state"] = STATE_ACTIVE
        timer["expiry"] = expiry.isoformat()
        del timer["remaining_duration"]

        await self._async_save()
        self._notify_sensor_update()

        _LOGGER.info("Resumed timer '%s'", name)

    async def cancel_timer(self, name: str) -> None:
        """Cancel a timer."""
        if name not in self._timers:
            _LOGGER.warning("Timer '%s' not found", name)
            return

        del self._timers[name]

        await self._async_save()
        self._notify_sensor_update()

        _LOGGER.info("Cancelled timer '%s'", name)

    async def extend_timer(
        self,
        name: str,
        add_duration: Optional[int] = None,
        new_expiry: Optional[str] = None,
    ) -> None:
        """Extend a timer."""
        if name not in self._timers:
            _LOGGER.warning("Timer '%s' not found", name)
            return

        if not add_duration and not new_expiry:
            _LOGGER.error("Must provide either add_duration or new_expiry")
            return

        timer = self._timers[name]

        if timer["state"] != STATE_ACTIVE:
            _LOGGER.warning("Timer '%s' is not active, cannot extend", name)
            return

        if new_expiry:
            # Validate new_expiry is a proper ISO timestamp
            try:
                # Try to parse the timestamp to validate it
                new_expiry_dt = datetime.fromisoformat(new_expiry)
                timer["expiry"] = new_expiry_dt.isoformat()
                _LOGGER.info("Set timer '%s' expiry to %s", name, new_expiry_dt.isoformat())
            except (ValueError, TypeError) as e:
                _LOGGER.error(
                    "Invalid new_expiry format '%s' for timer '%s': %s. "
                    "Expected ISO format like '2025-10-20T22:30:00'",
                    new_expiry, name, e
                )
                return
        elif add_duration:
            # Validate add_duration is a positive number
            if not isinstance(add_duration, (int, float)) or add_duration <= 0:
                _LOGGER.error(
                    "Invalid add_duration '%s' for timer '%s'. Must be a positive number.",
                    add_duration, name
                )
                return

            # Add duration to current expiry
            try:
                current_expiry = datetime.fromisoformat(timer["expiry"])
                new_expiry_time = current_expiry + timedelta(seconds=add_duration)
                timer["expiry"] = new_expiry_time.isoformat()
                _LOGGER.info("Extended timer '%s' by %d seconds", name, add_duration)
            except (ValueError, TypeError) as e:
                _LOGGER.error("Error extending timer '%s': %s", name, e)
                return

        await self._async_save()
        self._notify_sensor_update()

    async def pause_group(self, group: str) -> None:
        """Pause all timers in a group."""
        count = 0
        for name, timer in self._timers.items():
            if group in timer.get("groups", []):
                await self.pause_timer(name)
                count += 1

        _LOGGER.info("Paused %d timers in group '%s'", count, group)

    async def resume_group(self, group: str) -> None:
        """Resume all timers in a group."""
        count = 0
        for name, timer in self._timers.items():
            if group in timer.get("groups", []):
                await self.resume_timer(name)
                count += 1

        _LOGGER.info("Resumed %d timers in group '%s'", count, group)

    async def cancel_group(self, group: str) -> None:
        """Cancel all timers in a group."""
        timers_to_cancel = [
            name
            for name, timer in self._timers.items()
            if group in timer.get("groups", [])
        ]

        for name in timers_to_cancel:
            await self.cancel_timer(name)

        _LOGGER.info("Cancelled %d timers in group '%s'", len(timers_to_cancel), group)

    async def extend_group(
        self,
        group: str,
        add_duration: Optional[int] = None,
        new_expiry: Optional[str] = None,
    ) -> None:
        """Extend all timers in a group."""
        count = 0
        for name, timer in self._timers.items():
            if group in timer.get("groups", []):
                await self.extend_timer(name, add_duration, new_expiry)
                count += 1

        _LOGGER.info("Extended %d timers in group '%s'", count, group)
