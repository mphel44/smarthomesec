# SmartHomeSec

Python library and Home Assistant integration for SmartHomeSec/VESTA/Climax alarm systems.

## Project Structure

This repository contains two components:

```
smarthomesec/
├── py_smarthomesec/           # Standalone Python library
│   ├── py_smarthomesec/       # Library source code
│   ├── examples/              # Usage examples
│   └── tests/                 # Unit tests
└── custom_components/
    └── smarthomesec/          # Home Assistant integration
```

---

## py_smarthomesec Library

A production-quality async Python library for interacting with SmartHomeSec/VESTA alarm systems.

### Features

- Async HTTP client using `httpx`
- Automatic re-authentication on 401/403 errors
- Exponential retry on network failures
- WebSocket client for real-time notifications
- DataUpdateCoordinator for intelligent polling
- Pydantic models for type-safe data handling
- Full type hints (PEP 561 compliant)

### Installation

```bash
cd py_smarthomesec
pip install .
```

Or install dependencies manually:

```bash
pip install httpx pydantic tenacity websockets
```

### Quick Start

```python
import asyncio
from py_smarthomesec import SmartHomesecAPI

async def main():
    async with SmartHomesecAPI(username="user", password="pass") as client:
        # Get panel status
        status = await client.get_panel_status()

        # Display alarm state
        alarm = status.primary_alarm
        print(f"Alarm state: {alarm.state.value}")
        print(f"Armed: {alarm.is_armed}")

        # List devices
        for device in status.devices:
            print(f"Device: {device.name} ({device.device_type.value})")

        # Arm the alarm (requires PIN code)
        # await client.arm_away(pin_code="1234")

asyncio.run(main())
```

### WebSocket for Real-Time Events

```python
from py_smarthomesec import SmartHomesecAPI, WebSocketClient, WebSocketEvent

async def on_event(event: WebSocketEvent):
    print(f"Event: {event.event_type.value}")
    print(f"Data: {event.data}")

async def main():
    async with SmartHomesecAPI(username="user", password="pass") as client:
        token = client._auth.token

        ws_client = WebSocketClient(token=token, auto_reconnect=True)
        ws_client.on_event(on_event)

        await ws_client.connect()

        # Keep running...
        while ws_client.is_connected:
            await asyncio.sleep(1)

asyncio.run(main())
```

### Polling with DataUpdateCoordinator

```python
from py_smarthomesec import SmartHomesecAPI, PanelStatusCoordinator

async def main():
    async with SmartHomesecAPI(username="user", password="pass") as client:
        coordinator = PanelStatusCoordinator(api=client, update_interval=30)

        def on_update(result):
            if result.success:
                print(f"Devices: {len(result.data.devices)}")

        coordinator.add_listener(on_update)
        await coordinator.start()

        # Run for a while...
        await asyncio.sleep(300)

        await coordinator.stop()

asyncio.run(main())
```

### API Reference

#### SmartHomesecAPI

| Method | Description |
|--------|-------------|
| `get_panel_status()` | Get complete panel state (devices + alarms) |
| `set_alarm_mode(mode, pin_code, area)` | Set alarm mode |
| `arm_away(pin_code, area)` | Arm in away mode |
| `arm_home(pin_code, area)` | Arm in home mode |
| `disarm(pin_code, area)` | Disarm the alarm |
| `get_devices()` | Get device list |
| `get_alarm_areas()` | Get alarm area list |

#### Models

- `PanelStatus` - Complete panel state
- `AlarmArea` - Alarm zone with state
- `Device` - Base device class
- `ContactSensor` - Door/window sensor
- `PIRSensor` - Motion sensor
- `Keypad` - Alarm keypad
- `IPCamera` - IP camera

#### Exceptions

- `SmartHomesecError` - Base exception
- `AuthenticationError` - Auth failure
- `InvalidCredentialsError` - Wrong credentials
- `SessionExpiredError` - Session expired
- `ConnectionError` - Network error
- `TimeoutError` - Request timeout
- `RateLimitError` - Rate limited

---

## Home Assistant Integration

### Installation

#### Manual Installation

1. Copy the `custom_components/smarthomesec` folder to your Home Assistant `config/custom_components/` directory:

```bash
cp -r custom_components/smarthomesec /path/to/homeassistant/config/custom_components/
```

2. Install the py_smarthomesec library:

```bash
# Option 1: Install from the local directory
cd py_smarthomesec
pip install .

# Option 2: Copy to HA's deps (if using Docker/HAOS)
# The library will be auto-installed from requirements in manifest.json
# once it's published to PyPI
```

3. Restart Home Assistant

4. Go to **Settings > Devices & Services > Add Integration**

5. Search for "SmartHomeSec" and follow the setup wizard

### Configuration

The integration is configured via the UI. You'll need:

- **Name**: A friendly name for your alarm system
- **Username**: Your SmartHomeSec account username
- **Password**: Your SmartHomeSec account password

### Supported Entities

#### Alarm Control Panel
- Arm Away
- Arm Home
- Disarm (requires PIN code)
- Shows current state (armed, disarmed, triggered, etc.)

#### Binary Sensors
- Door/Window contacts (open/closed state)
- PIR motion sensors (motion detected/clear)

### Example Automations

#### Notify when door opens while armed

```yaml
automation:
  - alias: "Alert: Door opened while armed"
    trigger:
      - platform: state
        entity_id: binary_sensor.front_door
        to: "on"
    condition:
      - condition: state
        entity_id: alarm_control_panel.smarthomesec_1
        state: "armed_away"
    action:
      - service: notify.mobile_app
        data:
          title: "Security Alert"
          message: "Front door opened while alarm is armed!"
```

#### Auto-arm at night

```yaml
automation:
  - alias: "Auto arm at night"
    trigger:
      - platform: time
        at: "23:00:00"
    action:
      - service: alarm_control_panel.alarm_arm_home
        target:
          entity_id: alarm_control_panel.smarthomesec_1
        data:
          code: !secret alarm_pin
```

---

## Development

### Running Tests

```bash
cd py_smarthomesec
pip install pytest pytest-asyncio
pytest tests/ -v
```

### Project Dependencies

**Library (py_smarthomesec):**
- Python 3.11+
- httpx
- pydantic >= 2.0
- tenacity
- websockets

**Home Assistant Integration:**
- Home Assistant 2024.1+
- py_smarthomesec library

---

## License

MIT License

## Credits

- Original integration by [@koying](https://github.com/koying)
- Refactored library architecture
