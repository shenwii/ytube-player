"""Config flow and options flow for YouTube Player."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
import voluptuous as vol

from .const import (
    CONF_AUDIO_FORMAT,
    CONF_COOKIES,
    CONF_MAX_SEARCH_RESULTS,
    DEFAULT_AUDIO_FORMAT,
    DEFAULT_MAX_SEARCH_RESULTS,
    DOMAIN,
)
from .cookie_helper import get_cookie_file_path, sync_save_cookie_file

_LOGGER = logging.getLogger(__name__)


class YouTubePlayerConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for YouTube Player."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial setup step."""
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()

        if user_input is not None:
            # Save cookies to disk if provided
            cookies = user_input.get(CONF_COOKIES, "")
            cookie_path = get_cookie_file_path(self.hass)
            await self.hass.async_add_executor_job(
                sync_save_cookie_file, cookie_path, cookies
            )
            return self.async_create_entry(title="YouTube Player", data=user_input)

        schema = vol.Schema(
            {
                vol.Optional(CONF_COOKIES, default=""): str,
            }
        )

        return self.async_show_form(step_id="user", data_schema=schema)

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> YouTubePlayerOptionsFlow:
        """Get the options flow for this handler."""
        return YouTubePlayerOptionsFlow(config_entry)


class YouTubePlayerOptionsFlow(config_entries.OptionsFlow):
    """Handle options flow for YouTube Player."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage options."""
        if user_input is not None:
            cookies = user_input.get(CONF_COOKIES, "")
            cookie_path = get_cookie_file_path(self.hass)
            await self.hass.async_add_executor_job(
                sync_save_cookie_file, cookie_path, cookies
            )
            return self.async_create_entry(title="", data=user_input)

        current_config = {**self.config_entry.data, **self.config_entry.options}

        schema = vol.Schema(
            {
                vol.Optional(
                    CONF_COOKIES,
                    default=current_config.get(CONF_COOKIES, ""),
                ): str,
                vol.Optional(
                    CONF_MAX_SEARCH_RESULTS,
                    default=current_config.get(
                        CONF_MAX_SEARCH_RESULTS, DEFAULT_MAX_SEARCH_RESULTS
                    ),
                ): vol.All(vol.Coerce(int), vol.Range(min=1, max=50)),
                vol.Optional(
                    CONF_AUDIO_FORMAT,
                    default=current_config.get(
                        CONF_AUDIO_FORMAT, DEFAULT_AUDIO_FORMAT
                    ),
                ): str,
            }
        )

        return self.async_show_form(step_id="init", data_schema=schema)
