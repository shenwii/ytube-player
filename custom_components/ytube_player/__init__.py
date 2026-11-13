"""YouTube Player integration for Home Assistant."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
)
import voluptuous as vol

from .const import CONF_COOKIES, DOMAIN
from .cookie_helper import get_cookie_file_path, sync_save_cookie_file
from .media_source import async_search_playable_videos
from .view import YouTubeStreamView, clear_stream_cache

_LOGGER = logging.getLogger(__name__)

VIEW_REGISTERED = f"{DOMAIN}_view_registered"
SERVICE_SEARCH = "search"

SEARCH_SERVICE_SCHEMA = vol.Schema(
    {
        vol.Required("query"): str,
        vol.Optional("limit"): vol.All(vol.Coerce(int), vol.Range(min=1, max=50)),
    }
)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up YouTube Player from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    config_data = {**entry.data, **entry.options}
    hass.data[DOMAIN][entry.entry_id] = config_data

    # Ensure cookie file is initialized
    cookies = config_data.get(CONF_COOKIES, "")
    cookie_path = get_cookie_file_path(hass)
    await hass.async_add_executor_job(sync_save_cookie_file, cookie_path, cookies)

    # Register the HTTP stream proxy view once
    if not hass.data.get(VIEW_REGISTERED):
        hass.http.register_view(YouTubeStreamView(hass))
        hass.data[VIEW_REGISTERED] = True

    # Register search service once
    if not hass.services.has_service(DOMAIN, SERVICE_SEARCH):

        async def _async_handle_search(call: ServiceCall) -> ServiceResponse:
            query = str(call.data["query"]).strip()
            limit = call.data.get("limit")
            results = await async_search_playable_videos(hass, query, limit=limit)
            return {
                "query": query,
                "results": results,
            }

        hass.services.async_register(
            DOMAIN,
            SERVICE_SEARCH,
            _async_handle_search,
            schema=SEARCH_SERVICE_SCHEMA,
            supports_response=SupportsResponse.ONLY,
        )

    # Register update listener
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))
    clear_stream_cache()

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    hass.data[DOMAIN].pop(entry.entry_id, None)
    if not hass.data.get(DOMAIN) and hass.services.has_service(DOMAIN, SERVICE_SEARCH):
        hass.services.async_remove(DOMAIN, SERVICE_SEARCH)
    clear_stream_cache()
    return True


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the config entry after options change."""
    await hass.config_entries.async_reload(entry.entry_id)
