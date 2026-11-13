"""Media Source implementation for YouTube Player."""

from __future__ import annotations

import logging
import re
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

from homeassistant.components.media_player import (
    MediaClass,
    MediaType,
    SearchMedia,
    SearchMediaQuery,
)
from homeassistant.components.media_source import (
    BrowseMediaSource,
    MediaSource,
    MediaSourceItem,
    PlayMedia,
    Unresolvable,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.network import get_url
import yt_dlp

from .const import (
    CONF_AUDIO_FORMAT,
    CONF_COOKIES,
    CONF_MAX_SEARCH_RESULTS,
    DEFAULT_AUDIO_FORMAT,
    DEFAULT_MAX_SEARCH_RESULTS,
    DOMAIN,
)
from .cookie_helper import get_ydl_cookie_opts

_LOGGER = logging.getLogger(__name__)


def extract_youtube_video_id(url_or_id: str) -> str | None:
    """Extract YouTube 11-char video ID from URL or string if present."""
    url_or_id = url_or_id.strip()
    for ext in (".m4a", ".mp4", ".mp3", ".webm"):
        if url_or_id.endswith(ext):
            url_or_id = url_or_id[:-len(ext)]
            break

    if re.match(r"^[a-zA-Z0-9_-]{11}$", url_or_id):
        return url_or_id

    parsed = urlparse(url_or_id)
    if "youtube.com" in parsed.netloc:
        if parsed.path == "/watch":
            qs = parse_qs(parsed.query)
            v_list = qs.get("v")
            if v_list:
                return v_list[0]
        elif parsed.path.startswith("/shorts/"):
            parts = parsed.path.strip("/").split("/")
            if len(parts) >= 2:
                return parts[1]
    elif "youtu.be" in parsed.netloc:
        video_id = parsed.path.strip("/")
        if re.match(r"^[a-zA-Z0-9_-]{11}$", video_id):
            return video_id

    return None


async def async_get_media_source(hass: HomeAssistant) -> YouTubeMediaSource:
    """Set up the YouTube media source."""
    return YouTubeMediaSource(hass)


class YouTubeMediaSource(MediaSource):
    """Provide YouTube content as a media source."""

    name = "YouTube"

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the YouTube media source."""
        super().__init__(DOMAIN)
        self.hass = hass

    def _get_config_options(self) -> dict[str, Any]:
        """Retrieve stored configuration / options."""
        domain_data = self.hass.data.get(DOMAIN, {})
        for entry in domain_data.values():
            if isinstance(entry, dict):
                return entry
        return {}

    def _get_ydl_options(self, extra_opts: dict[str, Any] | None = None) -> dict[str, Any]:
        """Build standard options for YoutubeDL."""
        config = self._get_config_options()
        cookie_str = config.get(CONF_COOKIES)
        audio_format = config.get(CONF_AUDIO_FORMAT, DEFAULT_AUDIO_FORMAT)

        opts: dict[str, Any] = {
            "quiet": True,
            "no_warnings": True,
            "format": audio_format,
            "skip_download": True,
            "noplaylist": True,
            "extract_flat": False,
        }
        opts.update(get_ydl_cookie_opts(self.hass, cookie_str))
        if extra_opts:
            opts.update(extra_opts)
        return opts

    async def async_browse_media(self, item: MediaSourceItem) -> BrowseMediaSource:
        """Return root browse media item enabling search."""
        return BrowseMediaSource(
            domain=DOMAIN,
            identifier="",
            media_class=MediaClass.DIRECTORY,
            media_content_type=MediaType.MUSIC,
            title="YouTube",
            can_play=False,
            can_expand=True,
            can_search=True,
            children=[],
        )

    async def async_search_media(
        self, item: MediaSourceItem, query: SearchMediaQuery | str
    ) -> SearchMedia:
        """Search YouTube for matching videos."""
        if hasattr(query, "search_query"):
            search_str = query.search_query
        else:
            search_str = str(query)

        search_str = search_str.strip()
        if not search_str:
            return SearchMedia(result=[])

        config = self._get_config_options()
        max_results = config.get(CONF_MAX_SEARCH_RESULTS, DEFAULT_MAX_SEARCH_RESULTS)

        def _search() -> list[dict[str, Any]]:
            opts = self._get_ydl_options({"extract_flat": True})
            search_url = f"ytsearch{max_results}:{search_str}"
            results: list[dict[str, Any]] = []

            with yt_dlp.YoutubeDL(opts) as ydl:
                try:
                    info = ydl.extract_info(search_url, download=False)
                    if not info or "entries" not in info:
                        return results
                    for entry in info["entries"]:
                        if not entry or not entry.get("id"):
                            continue
                        thumb = None
                        thumbnails = entry.get("thumbnails")
                        if isinstance(thumbnails, list) and thumbnails:
                            thumb = thumbnails[-1].get("url")
                        elif entry.get("thumbnail"):
                            thumb = entry.get("thumbnail")

                        results.append(
                            {
                                "id": entry["id"],
                                "title": entry.get("title", "Unknown"),
                                "thumbnail": thumb,
                            }
                        )
                except Exception as err:
                    _LOGGER.error("Failed to search YouTube with query '%s': %s", search_str, err)

            return results

        video_entries = await self.hass.async_add_executor_job(_search)

        items: list[BrowseMediaSource] = []
        for v in video_entries:
            items.append(
                BrowseMediaSource(
                    domain=DOMAIN,
                    identifier=v["id"],
                    media_class=MediaClass.TRACK,
                    media_content_type=MediaType.MUSIC,
                    title=v["title"],
                    can_play=True,
                    can_expand=False,
                    thumbnail=v.get("thumbnail"),
                )
            )

        return SearchMedia(result=items)

    async def async_resolve_media(self, item: MediaSourceItem) -> PlayMedia:
        """Resolve a media item identifier into a local proxy audio stream URL."""
        raw_identifier = unquote(item.identifier or "").strip()
        if not raw_identifier:
            raise Unresolvable("No media identifier provided")

        # Check if it starts with search prefixes
        if raw_identifier.startswith("search?q="):
            search_query = raw_identifier[9:].strip()
            video_id = await self._async_search_first_video_id(search_query)
        elif raw_identifier.startswith("search/"):
            search_query = raw_identifier[7:].strip()
            video_id = await self._async_search_first_video_id(search_query)
        else:
            # Check if it is an explicit video ID or YouTube URL
            video_id = extract_youtube_video_id(raw_identifier)
            if not video_id:
                # If it's a search term passed directly without prefix
                video_id = await self._async_search_first_video_id(raw_identifier)

        if not video_id:
            raise Unresolvable(f"Could not resolve video ID for: {raw_identifier}")

        base_url = get_url(self.hass, prefer_external=False)
        play_url = f"{base_url}/api/ytube_player/stream/{video_id}.m4a"

        return PlayMedia(url=play_url, mime_type="audio/mp4")

    async def _async_search_first_video_id(self, query: str) -> str | None:
        """Search YouTube for the first video matching the query and return its video ID."""
        if not query.strip():
            return None

        def _search_first() -> str | None:
            opts = self._get_ydl_options({"extract_flat": True})
            search_url = f"ytsearch1:{query}"
            with yt_dlp.YoutubeDL(opts) as ydl:
                try:
                    info = ydl.extract_info(search_url, download=False)
                    if not info or "entries" not in info:
                        return None
                    entries = [e for e in info["entries"] if e]
                    if not entries:
                        return None
                    return entries[0].get("id")
                except Exception as err:
                    _LOGGER.error("Failed to search first video for query '%s': %s", query, err)
                    return None

        return await self.hass.async_add_executor_job(_search_first)
