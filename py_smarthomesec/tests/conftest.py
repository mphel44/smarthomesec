"""
Pytest fixtures for py_smarthomesec tests.
"""

import pytest


@pytest.fixture
def mock_credentials() -> dict[str, str]:
    """Return mock credentials for testing."""
    return {
        "username": "test_user",
        "password": "test_password",
    }


@pytest.fixture
def mock_login_response() -> dict:
    """Return a mock login response."""
    return {
        "token": "mock_token_12345",
        "data": {
            "user_id": "user_123",
            "user_name": "test_user",
            "account": "test_user",
        },
    }


@pytest.fixture
def mock_panel_response() -> dict:
    """Return a mock panel/cycle response."""
    return {
        "data": {
            "device_status": [
                {
                    "device_id": "DOOR_001",
                    "name": "Front Door",
                    "type": "device_type.door_contact",
                    "status_open": [],
                    "status_battery": "device_status.battery_ok",
                },
                {
                    "device_id": "PIR_001",
                    "name": "Living Room Motion",
                    "type": "device_type.pir",
                    "status_motion": "0",
                    "status_battery": "device_status.battery_ok",
                },
            ],
            "model": [
                {
                    "area": 1,
                    "mode": "disarm",
                    "area_name": "Home",
                },
            ],
        },
    }
