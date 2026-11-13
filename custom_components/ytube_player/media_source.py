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
from .view import async_ensure_audio_cached

_LOGGER = logging.getLogger(__name__)

_VIDEO_ID_RE = re.compile(r"^[a-zA-Z0-9_-]{11}$")
_UNPLAYABLE_LIVE_STATUSES = frozenset({"is_live", "is_upcoming", "post_live"})


def _is_playable_video_entry(entry: Any) -> bool:
    """Return True if a flat yt-dlp search entry is a playable single VOD video."""
    if not isinstance(entry, dict):
        return False

    entry_id = entry.get("id")
    if not isinstance(entry_id, str) or not _VIDEO_ID_RE.match(entry_id):
        return False

    if entry.get("_type") in ("playlist", "multi_video"):
        return False

    ie_key = entry.get("ie_key")
    if ie_key is not None and ie_key != "Youtube":
        return False

    url = entry.get("url")
    if isinstance(url, str) and (
        "/playlist" in url
        or "/channel/" in url
        or "/hashtag/" in url
        or "list=" in url
    ):
        return False

    if entry.get("is_live") is True:
        return False

    if entry.get("live_status") in _UNPLAYABLE_LIVE_STATUSES:
        return False

    return True


def extract_youtube_video_id(url_or_id: str) -> str | None:
    """Extract YouTube 11-char video ID from URL or string if present."""
    url_or_id = url_or_id.strip()
    for ext in (".m4a", ".mp4", ".mp3", ".webm"):
        if url_or_id.endswith(ext):
            url_or_id = url_or_id[:-len(ext)]
            break

    if _VIDEO_ID_RE.match(url_or_id):
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
        if _VIDEO_ID_RE.match(video_id):
            return video_id

    return None


async def async_get_media_source(hass: HomeAssistant) -> YouTubeMediaSource:
    """Set up the YouTube media source."""
    return YouTubeMediaSource(hass)


def _get_entry_config(hass: HomeAssistant) -> dict[str, Any]:
    """Retrieve stored configuration / options from hass.data."""
    domain_data = hass.data.get(DOMAIN, {})
    for entry in domain_data.values():
        if isinstance(entry, dict):
            return entry
    return {}


def _build_ydl_search_options(
    hass: HomeAssistant, extra_opts: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Build standard YoutubeDL options for search queries."""
    config = _get_entry_config(hass)
    cookie_str = config.get(CONF_COOKIES)
    audio_format = config.get(CONF_AUDIO_FORMAT, DEFAULT_AUDIO_FORMAT)

    opts: dict[str, Any] = {
        "quiet": True,
        "no_warnings": True,
        "format": audio_format,
        "skip_download": True,
        "noplaylist": True,
        "extract_flat": True,
    }
    opts.update(get_ydl_cookie_opts(hass, cookie_str))
    if extra_opts:
        opts.update(extra_opts)
    return opts


def _extract_search_query(raw_identifier: str) -> str | None:
    """Extract search query from search?q=... or search/... identifiers."""
    if raw_identifier.startswith("search?q="):
        return raw_identifier[9:].strip()
    if raw_identifier.startswith("search/"):
        return raw_identifier[7:].strip()
    return None


def _build_track_browse_items(video_entries: list[dict[str, Any]]) -> list[BrowseMediaSource]:
    """Convert search result dicts into playable BrowseMediaSource items."""
    return [
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
        for v in video_entries
    ]


async def async_search_playable_videos(
    hass: HomeAssistant,
    search_str: str,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    """Search YouTube and return up to limit playable single VOD videos."""
    cleaned = search_str.strip()
    if not cleaned:
        return []

    if limit is None:
        config = _get_entry_config(hass)
        limit = int(config.get(CONF_MAX_SEARCH_RESULTS, DEFAULT_MAX_SEARCH_RESULTS))
    limit = max(1, min(int(limit), 50))

    def _search() -> list[dict[str, Any]]:
        opts = _build_ydl_search_options(hass)
        fetch_limit = min(max(limit * 2, 10), 50)
        search_url = f"ytsearch{fetch_limit}:{cleaned}"
        results: list[dict[str, Any]] = []

        with yt_dlp.YoutubeDL(opts) as ydl:
            try:
                info = ydl.extract_info(search_url, download=False)
                if not info or "entries" not in info:
                    return results
                for entry in info["entries"]:
                    if not _is_playable_video_entry(entry):
                        continue
                    thumb = None
                    thumbnails = entry.get("thumbnails")
                    if isinstance(thumbnails, list) and thumbnails:
                        thumb = thumbnails[-1].get("url")
                    elif entry.get("thumbnail"):
                        thumb = entry.get("thumbnail")

                    video_id = entry["id"]
                    results.append(
                        {
                            "id": video_id,
                            "title": entry.get("title", "Unknown"),
                            "thumbnail": thumb,
                        }
                    )
                    if len(results) >= limit:
                        break
            except Exception as err:
                _LOGGER.error("Failed to search YouTube with query '%s': %s", cleaned, err)

        return results

    return await hass.async_add_executor_job(_search)


class YouTubeMediaSource(MediaSource):
    """Provide YouTube content as a media source."""

    name = "YouTube"

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the YouTube media source."""
        super().__init__(DOMAIN)
        self.hass = hass

    async def async_browse_media(self, item: MediaSourceItem) -> BrowseMediaSource:
        """Return root browse media item or search results for search identifiers."""
        raw_identifier = unquote(item.identifier or "").strip()
        if not raw_identifier:
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

        search_query = _extract_search_query(raw_identifier)
        if search_query is None:
            video_id = extract_youtube_video_id(raw_identifier)
            if video_id:
                return BrowseMediaSource(
                    domain=DOMAIN,
                    identifier=video_id,
                    media_class=MediaClass.TRACK,
                    media_content_type=MediaType.MUSIC,
                    title=video_id,
                    can_play=True,
                    can_expand=False,
                )
            search_query = raw_identifier

        video_entries = await async_search_playable_videos(self.hass, search_query)
        return BrowseMediaSource(
            domain=DOMAIN,
            identifier=raw_identifier,
            media_class=MediaClass.DIRECTORY,
            media_content_type=MediaType.MUSIC,
            title=f"YouTube: {search_query}",
            can_play=False,
            can_expand=True,
            can_search=True,
            children=_build_track_browse_items(video_entries),
        )

    async def async_search_media(
        self, item: MediaSourceItem, query: SearchMediaQuery | str
    ) -> SearchMedia:
        """Search YouTube for matching videos."""
        if hasattr(query, "search_query"):
            search_str = query.search_query
        else:
            search_str = str(query)

        video_entries = await async_search_playable_videos(self.hass, search_str)
        return SearchMedia(result=_build_track_browse_items(video_entries))

    async def async_resolve_media(self, item: MediaSourceItem) -> PlayMedia:
        """Resolve a media item identifier into a local proxy audio stream URL."""
        raw_identifier = unquote(item.identifier or "").strip()
        if not raw_identifier:
            raise Unresolvable("No media identifier provided")

        search_query = _extract_search_query(raw_identifier)
        if search_query is not None:
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

        async def _precache() -> None:
            try:
                await async_ensure_audio_cached(self.hass, video_id)
            except Exception as err:
                _LOGGER.debug("Background pre-cache failed for %s: %s", video_id, err)

        if hasattr(self.hass, "async_create_task"):
            self.hass.async_create_task(_precache())

        return PlayMedia(url=play_url, mime_type="audio/mp4")

    async def _async_search_first_video_id(self, query: str) -> str | None:
        """Search YouTube for the first playable video matching the query and return its ID."""
        entries = await async_search_playable_videos(self.hass, query, limit=1)
        return entries[0]["id"] if entries else None
