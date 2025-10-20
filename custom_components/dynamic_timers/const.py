"""Constants for the Dynamic Timers integration."""

DOMAIN = "dynamic_timers"
STORAGE_KEY = "dynamic_timers.timers"
STORAGE_VERSION = 1

# Timer states
STATE_ACTIVE = "active"
STATE_PAUSED = "paused"

# Restart behaviors
RESTART_RESUME = "resume"  # Continue timer, execute if expired
RESTART_SKIP = "skip"  # Discard timer if expired
RESTART_EXECUTE = "execute"  # Always execute immediately

# Action types
ACTION_EVENT = "event"
ACTION_SERVICE = "service"

# Update interval for checking timers (seconds)
CHECK_INTERVAL = 1
