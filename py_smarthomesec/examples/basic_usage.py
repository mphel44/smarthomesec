"""
Basic usage example for py_smarthomesec.
"""

import asyncio
import logging

from py_smarthomesec import (
    DeviceType,
    InvalidCredentialsError,
    SmartHomesecAPI,
    SmartHomesecError,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)


async def main() -> None:
    """Example usage of the SmartHomeSec client."""

    # Replace with your credentials
    username = "your_username"
    password = "your_password"
    pin_code = "1234"

    try:
        # Use context manager (recommended)
        async with SmartHomesecAPI(username=username, password=password) as client:
            # Get complete panel state
            status = await client.get_panel_status()

            # Display primary alarm state
            alarm = status.primary_alarm
            if alarm:
                print(f"Alarm zone: {alarm.area_name or f'Zone {alarm.area}'}")
                print(f"State: {alarm.state.value}")
                print(f"Armed: {alarm.is_armed}")
                print(f"Triggered: {alarm.is_triggered}")

            # List devices
            print(f"\nDevices ({len(status.devices)}):")
            for device in status.devices:
                print(f"  - {device.name} ({device.device_type.value})")

                # Display specific state based on type
                if device.device_type == DeviceType.DOOR_CONTACT:
                    print(f"    State: {'Open' if device.is_open else 'Closed'}")
                elif device.device_type == DeviceType.PIR:
                    print(f"    Motion: {'Yes' if device.motion_detected else 'No'}")

            # Example: Arm the alarm in away mode
            # Uncomment to test (warning: this actually arms the alarm!)
            # await client.arm_away(pin_code)
            # print("\nAlarm armed in away mode")

            # Example: Disarm the alarm
            # await client.disarm(pin_code)
            # print("\nAlarm disarmed")

    except InvalidCredentialsError:
        print("Error: Invalid credentials")
    except SmartHomesecError as e:
        print(f"SmartHomeSec error: {e}")


if __name__ == "__main__":
    asyncio.run(main())
