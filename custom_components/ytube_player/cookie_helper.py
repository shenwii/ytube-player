"""Cookie parsing and storage helpers for YouTube Player."""

from __future__ import annotations

import logging
import os
import time
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

COOKIE_STORAGE_FILE = "ytube_player_cookies.txt"


def get_cookie_file_path(hass: HomeAssistant) -> str:
    """Return the absolute path to the stored cookies file."""
    return hass.config.path(".storage", COOKIE_STORAGE_FILE)


def cookie_string_to_netscape(cookie_str: str) -> str:
    """Convert raw Cookie header or string into Netscape HTTP Cookie format."""
    if not cookie_str or not cookie_str.strip():
        return ""

    cleaned = cookie_str.replace("\r\n", "\n").replace("\r", "\n").strip()

    # If already in Netscape format
    if "# Netscape" in cleaned or "\t" in cleaned:
        return cleaned + "\n"

    # Strip leading 'Cookie:' or 'cookie:' if user pasted the entire header line
    if cleaned.lower().startswith("cookie:"):
        cleaned = cleaned[7:].strip()

    expire = int(time.time()) + 365 * 24 * 3600
    lines = [
        "# Netscape HTTP Cookie File",
        "# Created for YouTube Player Home Assistant Integration",
        "",
    ]

    for item in cleaned.split(";"):
        item = item.strip()
        if not item or "=" not in item:
            continue
        key, val = item.split("=", 1)
        key = key.strip()
        val = val.strip()
        if not key:
            continue
        # Scope cookie to .youtube.com
        lines.append(f".youtube.com\tTRUE\t/\tTRUE\t{expire}\t{key}\t{val}")

    return "\n".join(lines) + "\n"


def sync_save_cookie_file(cookie_path: str, cookie_str: str) -> str | None:
    """Save the cookie string to disk as a Netscape cookie file."""
    if not cookie_str or not cookie_str.strip():
        if os.path.exists(cookie_path):
            try:
                os.remove(cookie_path)
            except OSError as err:
                _LOGGER.warning("Could not remove old cookie file: %s", err)
        return None

    netscape_content = cookie_string_to_netscape(cookie_str)
    try:
        os.makedirs(os.path.dirname(cookie_path), exist_ok=True)
        with open(cookie_path, "w", encoding="utf-8") as f:
            f.write(netscape_content)
        return cookie_path
    except OSError as err:
        _LOGGER.error("Failed to save cookies to %s: %s", cookie_path, err)
        return None


def get_ydl_cookie_opts(hass: HomeAssistant, cookie_str: str | None) -> dict[str, Any]:
    """Get yt-dlp cookie options based on configuration."""
    opts: dict[str, Any] = {}
    if not cookie_str or not cookie_str.strip():
        return opts

    cookie_path = get_cookie_file_path(hass)
    if os.path.exists(cookie_path):
        opts["cookiefile"] = cookie_path
    else:
        # Fallback to direct http header
        cleaned = cookie_str.strip()
        if cleaned.lower().startswith("cookie:"):
            cleaned = cleaned[7:].strip()
        opts["http_headers"] = {"Cookie": cleaned}

    return opts
