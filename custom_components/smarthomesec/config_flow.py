"""Config flow for SmartHomeSec integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from py_smarthomesec import SmartHomesecAPI, InvalidCredentialsError, SmartHomesecError

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_NAME, CONF_PASSWORD, CONF_USERNAME

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME): str,
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


class SmartHomesecConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for SmartHomeSec."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Check for existing entries with same credentials
            self._async_abort_entries_match(
                {CONF_USERNAME: user_input[CONF_USERNAME]}
            )

            username = user_input[CONF_USERNAME]
            password = user_input[CONF_PASSWORD]

            try:
                await self._test_credentials(username, password)
            except InvalidCredentialsError:
                errors["base"] = "invalid_auth"
            except SmartHomesecError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception during authentication")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    title=user_input[CONF_NAME],
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=DATA_SCHEMA,
            errors=errors,
        )

    async def _test_credentials(self, username: str, password: str) -> None:
        """Test if credentials are valid."""
        api = SmartHomesecAPI(username=username, password=password)
        try:
            await api.connect()
            # If connection succeeds, credentials are valid
        finally:
            await api.disconnect()
