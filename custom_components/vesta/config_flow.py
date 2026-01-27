"""Config flow for VESTA Alarm Panel integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .api.client import VestaApiClient
from .api.exceptions import (
    VestaAuthenticationError,
    VestaConnectionError,
    VestaError,
)
from .const import DOMAIN, CONF_PIN_CODE

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): TextSelector(
            TextSelectorConfig(type=TextSelectorType.EMAIL)
        ),
        vol.Required(CONF_PASSWORD): TextSelector(
            TextSelectorConfig(type=TextSelectorType.PASSWORD)
        ),
        vol.Optional(CONF_PIN_CODE): TextSelector(
            TextSelectorConfig(type=TextSelectorType.PASSWORD)
        ),
    }
)

STEP_REAUTH_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_PASSWORD): TextSelector(
            TextSelectorConfig(type=TextSelectorType.PASSWORD)
        ),
    }
)


async def validate_credentials(
    username: str,
    password: str,
) -> dict[str, str]:
    """Validate the user credentials.

    Returns:
        dict with any errors keyed by field name.
    """
    errors: dict[str, str] = {}

    client = VestaApiClient(username=username, password=password)

    try:
        await client.async_test_connection()
    except VestaAuthenticationError:
        errors["base"] = "invalid_auth"
    except VestaConnectionError:
        errors["base"] = "cannot_connect"
    except VestaError as err:
        _LOGGER.exception("Unexpected VESTA error: %s", err)
        errors["base"] = "unknown"
    except Exception:
        _LOGGER.exception("Unexpected error during validation")
        errors["base"] = "unknown"
    finally:
        await client.close()

    return errors


class VestaConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for VESTA Alarm Panel."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._reauth_entry: ConfigEntry | None = None

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> VestaOptionsFlow:
        """Get the options flow for this handler."""
        return VestaOptionsFlow(config_entry)

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Check if already configured with this username
            await self.async_set_unique_id(user_input[CONF_USERNAME].lower())
            self._abort_if_unique_id_configured()

            # Validate credentials
            errors = await validate_credentials(
                user_input[CONF_USERNAME],
                user_input[CONF_PASSWORD],
            )

            if not errors:
                return self.async_create_entry(
                    title=f"VESTA ({user_input[CONF_USERNAME]})",
                    data={
                        CONF_USERNAME: user_input[CONF_USERNAME],
                        CONF_PASSWORD: user_input[CONF_PASSWORD],
                    },
                    options={
                        CONF_PIN_CODE: user_input.get(CONF_PIN_CODE, ""),
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )

    async def async_step_reauth(
        self,
        entry_data: dict[str, Any],
    ) -> ConfigFlowResult:
        """Handle re-authentication flow.

        This is triggered when ConfigEntryAuthFailed is raised.
        """
        self._reauth_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Handle re-authentication confirmation."""
        errors: dict[str, str] = {}

        if self._reauth_entry is None:
            return self.async_abort(reason="reauth_failed")

        if user_input is not None:
            username = self._reauth_entry.data[CONF_USERNAME]

            # Validate new password
            errors = await validate_credentials(
                username,
                user_input[CONF_PASSWORD],
            )

            if not errors:
                # Update the config entry with new password
                self.hass.config_entries.async_update_entry(
                    self._reauth_entry,
                    data={
                        **self._reauth_entry.data,
                        CONF_PASSWORD: user_input[CONF_PASSWORD],
                    },
                )
                await self.hass.config_entries.async_reload(
                    self._reauth_entry.entry_id
                )
                return self.async_abort(reason="reauth_successful")

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=STEP_REAUTH_DATA_SCHEMA,
            errors=errors,
            description_placeholders={
                "username": self._reauth_entry.data.get(CONF_USERNAME, ""),
            },
        )


class VestaOptionsFlow(OptionsFlow):
    """Handle options flow for VESTA integration."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current_pin = self.config_entry.options.get(
            CONF_PIN_CODE,
            self.config_entry.data.get(CONF_PIN_CODE, ""),
        )

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_PIN_CODE,
                        default=current_pin,
                    ): TextSelector(
                        TextSelectorConfig(type=TextSelectorType.PASSWORD)
                    ),
                }
            ),
        )
