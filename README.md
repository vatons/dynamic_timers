# Dynamic Timers for Home Assistant

A Home Assistant custom integration that creates fully programmable, persistent timers that can be created and managed at runtime without configuration file changes or restarts.

## Features

- **Dynamic Timer Creation**: Create timers programmatically via service calls (no YAML configuration needed)
- **Persistent Storage**: Timers survive Home Assistant restarts with configurable behavior
- **Action Execution**: Execute actions when timers expire (fire events or call services)
- **Timer Management**: Pause, resume, cancel, and extend timers on the fly
- **Group Operations**: Organize timers into groups for batch control
- **Template Support**: Use Home Assistant templates in action data
- **Real-time Monitoring**: Sensor entity shows all active timers with remaining times

## Installation

### HACS (Recommended)

1. Open HACS in Home Assistant
2. Go to "Integrations"
3. Click the three dots in the top right and select "Custom repositories"
4. Add this repository URL and select "Integration" as the category
5. Click "Install"
6. Restart Home Assistant

### Manual Installation

1. Copy the `custom_components/dynamic_timers` directory to your Home Assistant `custom_components` directory
2. Restart Home Assistant

## Configuration

Add to your `configuration.yaml`:

```yaml
dynamic_timers:
```

That's it! No further configuration needed.

## Usage

### Entities

The integration creates two entities:

- **`sensor.dynamic_timers`**: Shows count of active timers with full timer details in attributes
- **`binary_sensor.dynamic_timers_ready`**: Shows when the system is ready after restart

### Services

#### `dynamic_timers.create`

Create a new timer that executes actions when it expires.

**Parameters:**

| Parameter | Required | Description | Example |
|-----------|----------|-------------|---------|
| `name` | No | Unique timer name (auto-generated if omitted) | `living_room_light` |
| `duration` | Yes | Duration in seconds | `300` |
| `actions` | Yes | List of actions to execute on expiry (can be a single dict or list) | See examples below |
| `restart_behavior` | No | What to do on HA restart: `resume`, `skip`, or `execute` (default: `resume`) | `resume` |
| `groups` | No | List of group names for batch operations | `["lights", "safety"]` |

**Example - Single action (simplified format):**

```yaml
service: dynamic_timers.create
data:
  name: living_room_auto_off
  duration: 300
  actions:
    action: light.turn_off
    target:
      entity_id: light.living_room
    data:
      transition: 5
```

**Example - Single action (list format):**

```yaml
service: dynamic_timers.create
data:
  name: living_room_auto_off
  duration: 300
  actions:
    - action: light.turn_off
      target:
        entity_id: light.living_room
      data:
        transition: 5
```

**Example - Turn off light (legacy format with action_type):**

```yaml
service: dynamic_timers.create
data:
  name: living_room_auto_off
  duration: 300
  actions:
    - action_type: service
      service: light.turn_off
      target:
        entity_id: light.living_room
      data:
        transition: 5
```

**Example - Fire event when timer expires:**

```yaml
service: dynamic_timers.create
data:
  name: motion_timeout
  duration: 600
  actions:
    - event: motion_timer_expired
      event_data:
        room: living_room
        timestamp: "{{ now().isoformat() }}"
```

**Example - Fire event (legacy format):**

```yaml
service: dynamic_timers.create
data:
  name: motion_timeout
  duration: 600
  actions:
    - action_type: event
      event: motion_timer_expired
      event_data:
        room: living_room
        timestamp: "{{ now().isoformat() }}"
```

**Example - Multiple actions with groups (modern format):**

```yaml
service: dynamic_timers.create
data:
  name: safety_check
  duration: 1800
  groups:
    - safety
    - notifications
  restart_behavior: execute
  actions:
    - action: lock.lock
      target:
        entity_id: lock.front_door
    - action: notify.mobile_app
      data:
        message: "Front door auto-locked after 30 minutes"
    - event: safety_timer_completed
```

#### `dynamic_timers.pause`

Pause an active timer or all timers in a group.

```yaml
# Pause a single timer
service: dynamic_timers.pause
data:
  name: living_room_auto_off

# Pause all timers in a group
service: dynamic_timers.pause
data:
  group: lights
```

#### `dynamic_timers.resume`

Resume a paused timer or all timers in a group.

```yaml
# Resume a single timer
service: dynamic_timers.resume
data:
  name: living_room_auto_off

# Resume all timers in a group
service: dynamic_timers.resume
data:
  group: lights
```

#### `dynamic_timers.cancel`

Cancel a timer or all timers in a group. Actions will not be executed.

```yaml
# Cancel a single timer
service: dynamic_timers.cancel
data:
  name: living_room_auto_off

# Cancel all timers in a group
service: dynamic_timers.cancel
data:
  group: lights
```

#### `dynamic_timers.extend`

Extend a timer by adding duration or setting a new expiry time.

```yaml
# Add 5 minutes to a timer
service: dynamic_timers.extend
data:
  name: living_room_auto_off
  add_duration: 300

# Set a new absolute expiry time
service: dynamic_timers.extend
data:
  name: living_room_auto_off
  new_expiry: "2025-10-20T23:00:00"

# Extend all timers in a group
service: dynamic_timers.extend
data:
  group: lights
  add_duration: 600
```

## Use Cases

### Auto-off for Lights

Create a timer when motion is detected, cancel it if motion continues:

```yaml
automation:
  - alias: "Living Room Motion - Start Timer"
    trigger:
      - platform: state
        entity_id: binary_sensor.living_room_motion
        to: "on"
    action:
      - service: light.turn_on
        target:
          entity_id: light.living_room
      - service: dynamic_timers.create
        data:
          name: living_room_motion_timer
          duration: 300
          groups: ["motion_lights"]
          actions:
            - action_type: service
              service: light.turn_off
              target:
                entity_id: light.living_room

  - alias: "Living Room Motion - Reset Timer"
    trigger:
      - platform: state
        entity_id: binary_sensor.living_room_motion
        to: "on"
    action:
      - service: dynamic_timers.cancel
        data:
          name: living_room_motion_timer
      - service: dynamic_timers.create
        data:
          name: living_room_motion_timer
          duration: 300
          groups: ["motion_lights"]
          actions:
            - action_type: service
              service: light.turn_off
              target:
                entity_id: light.living_room
```

### Safety Timeout

Lock doors automatically if left unlocked:

```yaml
automation:
  - alias: "Front Door Unlocked - Safety Timer"
    trigger:
      - platform: state
        entity_id: lock.front_door
        to: "unlocked"
    action:
      - service: dynamic_timers.create
        data:
          name: front_door_auto_lock
          duration: 1800
          restart_behavior: execute
          groups: ["safety"]
          actions:
            - action_type: service
              service: lock.lock
              target:
                entity_id: lock.front_door
            - action_type: service
              service: notify.mobile_app
              data:
                message: "Front door auto-locked after 30 minutes"
```

### Pause All Timers on Presence

Pause all timer groups when you're home, resume when away:

```yaml
automation:
  - alias: "Presence - Manage Timers"
    trigger:
      - platform: state
        entity_id: binary_sensor.someone_home
    action:
      - choose:
          - conditions:
              - condition: state
                entity_id: binary_sensor.someone_home
                state: "on"
            sequence:
              - service: dynamic_timers.pause
                data:
                  group: lights
              - service: dynamic_timers.pause
                data:
                  group: safety
          - conditions:
              - condition: state
                entity_id: binary_sensor.someone_home
                state: "off"
            sequence:
              - service: dynamic_timers.resume
                data:
                  group: lights
              - service: dynamic_timers.resume
                data:
                  group: safety
```

### Monitor Active Timers

Create a dashboard card to show all active timers:

```yaml
type: entities
entities:
  - entity: sensor.dynamic_timers
    name: Active Timers
    secondary_info: last-changed
  - entity: binary_sensor.dynamic_timers_ready
    name: System Ready
```

View timer details in attributes:

```yaml
type: markdown
content: |
  {% for timer_name, timer in state_attr('sensor.dynamic_timers', 'timers').items() %}
  ## {{ timer_name }}
  - **State**: {{ timer.state }}
  - **Expiry**: {{ timer.expiry if timer.expiry is defined else 'N/A' }}
  - **Groups**: {{ timer.groups | join(', ') if timer.groups else 'None' }}
  - **Restart Behavior**: {{ timer.restart_behavior }}
  - **Actions**: {{ timer.actions | length }} action(s)
  {% endfor %}
```

**Sensor Attributes Structure:**

Each timer in the `sensor.dynamic_timers` attributes includes:
- `name` - Timer identifier
- `state` - Current state (`active` or `paused`)
- `expiry` - ISO timestamp when timer expires (for active timers)
- `paused_duration` - Seconds remaining (for paused timers)
- `groups` - List of groups this timer belongs to
- `restart_behavior` - What happens on restart (`resume`, `skip`, or `execute`)
- `actions` - Full list of actions that will be executed

## Restart Behavior

Timers use **absolute timestamps** instead of countdowns, so they automatically continue after Home Assistant restarts. The `restart_behavior` setting controls what happens to timers:

- **`resume`** (default): Active timers continue running. If a timer expired while HA was down, its actions are executed immediately on restart.
- **`skip`**: Active timers continue running. If a timer expired while HA was down, it is discarded without executing actions.
- **`execute`**: Timer actions are executed immediately on restart regardless of expiry time.

**Examples:**

```yaml
# Default behavior - timer continues, executes if it expired during restart
service: dynamic_timers.create
data:
  name: auto_lock
  duration: 1800
  restart_behavior: resume  # or omit (default)
  actions:
    - action: lock.lock
      target:
        entity_id: lock.front_door

# Safety-critical timer that always executes on restart
service: dynamic_timers.create
data:
  name: critical_shutdown
  duration: 3600
  restart_behavior: execute
  actions:
    - action: switch.turn_off
      target:
        entity_id: switch.water_heater

# Temporary timer that gets discarded if expired during restart
service: dynamic_timers.create
data:
  name: temp_notification
  duration: 300
  restart_behavior: skip
  actions:
    - action: notify.mobile_app
      data:
        message: "Timer expired"
```

## Using Templates in Actions

Templates in action data are **always rendered when the timer expires** (at execution time), not when the timer is created. This means templates will use the current state when the timer actually fires.

### Important: Preventing Home Assistant from Pre-Rendering Templates

When you use `{{ }}` syntax in the Home Assistant UI or YAML, Home Assistant may render templates **before** sending them to the service. To prevent this and ensure templates are rendered at timer expiration, use **raw template syntax**:

**Method 1: Raw template blocks (Recommended)**

```yaml
service: dynamic_timers.create
data:
  name: notification_timer
  duration: 300
  actions:
    action: notify.mobile_app
    data:
      message: "{% raw %}Current time: {{ now().strftime('%H:%M:%S') }}{% endraw %}"
      title: "{% raw %}Temperature: {{ states('sensor.temperature') }}°C{% endraw %}"
```

**Method 2: Single quotes in YAML**

```yaml
service: dynamic_timers.create
data:
  name: notification_timer
  duration: 300
  actions:
    action: notify.mobile_app
    data:
      message: '{{ now().strftime("%H:%M:%S") }}'  # Single quotes prevent YAML processing
```

**Example - Send notification with current time when timer expires:**

```yaml
service: dynamic_timers.create
data:
  name: delayed_notification
  duration: 60
  actions:
    action: notify.mobile_app_s24_ultra
    data:
      message: "{% raw %}Timer expired at {{ now() }}{% endraw %}"
```

**Example - Control device based on current state:**

```yaml
service: dynamic_timers.create
data:
  name: conditional_lights
  duration: 1800
  actions:
    action: light.turn_off
    target:
      entity_id: "{% raw %}{{ area_entities('living_room') | select('match', 'light.') | list }}{% endraw %}"
```

## Advanced Examples

### Cascading Timers

Create a timer that starts another timer when it expires:

```yaml
service: dynamic_timers.create
data:
  name: first_timer
  duration: 300
  actions:
    - action_type: event
      event: first_timer_expired
    - action_type: service
      service: dynamic_timers.create
      data:
        name: second_timer
        duration: 300
        actions:
          - action_type: service
            service: light.turn_off
            target:
              entity_id: light.bedroom
```

### Conditional Actions Based on State

Use templates to conditionally execute actions (using raw template syntax):

```yaml
service: dynamic_timers.create
data:
  name: conditional_timer
  duration: 600
  actions:
    action: notify.mobile_app
    data:
      message: >
        {% raw %}{% if is_state('binary_sensor.door', 'on') %}
        Warning: Door still open after 10 minutes!
        {% else %}
        Door was closed properly.
        {% endif %}{% endraw %}
```

## Troubleshooting

### Timer not executing

- Check Home Assistant logs for errors
- Verify the timer exists: check `sensor.dynamic_timers` attributes
- Ensure `binary_sensor.dynamic_timers_ready` is `on`

### Timer lost after restart

- Check `restart_behavior` - default is `resume` which continues timers
- Use `skip` to discard expired timers or `execute` to always run on restart

### Templates not working or rendering too early

- **Use `{% raw %}` blocks** around templates to prevent Home Assistant from rendering them at service call time
- Example: `message: "{% raw %}{{ now() }}{% endraw %}"`
- Alternative: Use single quotes in YAML: `message: '{{ now() }}'`
- Check template syntax in Home Assistant Template Dev Tools
- Review logs for template rendering errors

## Contributing

Contributions are welcome! Please open an issue or pull request on GitHub.

## License

MIT License

## Support

For issues and feature requests, please use the [GitHub issue tracker](https://github.com/vatons/dynamic_timers/issues).
