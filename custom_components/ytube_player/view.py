"""HTTP View for proxying YouTube audio streams to media players."""

from __future__ import annotations

import logging
import time
from typing import Any

from aiohttp import web
from homeassistant.components.http import HomeAssistantView
from homeassistant.core import HomeAssistant
import yt_dlp

from .const import CONF_AUDIO_FORMAT, CONF_COOKIES, DEFAULT_AUDIO_FORMAT, DOMAIN
from .cookie_helper import get_ydl_cookie_opts

_LOGGER = logging.getLogger(__name__)

# In-memory cache for resolved stream info: video_id -> (expire_time, info_dict)
_STREAM_CACHE: dict[str, tuple[float, dict[str, Any]]] = {}
CACHE_TTL = 900  # 15 minutes


class YouTubeStreamView(HomeAssistantView):
    """View to proxy audio streams from YouTube."""

    url = "/api/ytube_player/stream/{video_id}"
    name = "api:ytube_player:stream"
    requires_auth = False

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the stream view."""
        self.hass = hass

    def _clean_video_id(self, video_id: str) -> str:
        """Strip audio file extensions like .m4a from video_id."""
        cleaned = video_id.strip()
        for ext in (".m4a", ".mp4", ".mp3", ".webm"):
            if cleaned.endswith(ext):
                return cleaned[:-len(ext)]
        return cleaned

    async def head(self, request: web.Request, video_id: str) -> web.Response:
        """Handle pre-flight HEAD requests from smart speakers like Sonos."""
        return web.Response(
            status=200,
            headers={
                "Content-Type": "audio/mp4",
                "Accept-Ranges": "bytes",
            },
        )

    async def get(self, request: web.Request, video_id: str) -> web.StreamResponse:
        """Stream the audio for the given video_id."""
        if not video_id:
            return web.Response(status=400, text="Missing video_id")

        video_id = self._clean_video_id(video_id)

        # Get integration options/config
        domain_data = self.hass.data.get(DOMAIN, {})
        entry_data = {}
        for entry in domain_data.values():
            if isinstance(entry, dict):
                entry_data = entry
                break

        cookie_str = entry_data.get(CONF_COOKIES)
        audio_format = entry_data.get(CONF_AUDIO_FORMAT, DEFAULT_AUDIO_FORMAT)

        now = time.time()
        cached = _STREAM_CACHE.get(video_id)
        if cached and cached[0] > now:
            info = cached[1]
        else:
            def _extract_stream_url() -> dict[str, Any] | None:
                ydl_opts: dict[str, Any] = {
                    "quiet": True,
                    "no_warnings": True,
                    "format": audio_format,
                    "skip_download": True,
                    "noplaylist": True,
                }
                ydl_opts.update(get_ydl_cookie_opts(self.hass, cookie_str))

                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    try:
                        extracted = ydl.extract_info(
                            f"https://www.youtube.com/watch?v={video_id}",
                            download=False,
                        )
                        return extracted
                    except Exception as err:
                        _LOGGER.error("Error extracting audio stream for %s: %s", video_id, err)
                        return None

            info = await self.hass.async_add_executor_job(_extract_stream_url)
            if not info or "url" not in info:
                return web.Response(status=404, text="Could not resolve audio stream")

            _STREAM_CACHE[video_id] = (now + CACHE_TTL, info)

        direct_url = info["url"]
        content_type = info.get("ext")

        # Always enforce an audio/* MIME type!
        # YouTube CDN upstream returns "video/mp4" for DASH format 140, which causes
        # audio-only speakers like Sonos to reject the stream with "UPnP Error 714: Illegal MIME-Type".
        if content_type == "m4a":
            mime_type = "audio/mp4"
        elif content_type in ("webm", "opus"):
            mime_type = "audio/webm"
        elif content_type == "mp3":
            mime_type = "audio/mpeg"
        else:
            mime_type = "audio/mp4"

        # Prepare upstream headers for YouTube CDN
        upstream_headers: dict[str, str] = {}
        if info.get("http_headers"):
            upstream_headers.update(info["http_headers"])

        if cookie_str and "Cookie" not in upstream_headers:
            cleaned_cookie = cookie_str.strip()
            if cleaned_cookie.lower().startswith("cookie:"):
                cleaned_cookie = cleaned_cookie[7:].strip()
            if "# Netscape" not in cleaned_cookie:
                upstream_headers["Cookie"] = cleaned_cookie

        if "range" in request.headers:
            upstream_headers["Range"] = request.headers["range"]

        # Proxy the stream using Home Assistant aiohttp client session
        session = self.hass.helpers.aiohttp_client.async_get_clientsession()
        try:
            async with session.get(direct_url, headers=upstream_headers) as upstream_resp:
                response = web.StreamResponse(
                    status=upstream_resp.status,
                    headers={
                        "Content-Type": mime_type,
                        "Accept-Ranges": "bytes",
                    },
                )
                if "Content-Length" in upstream_resp.headers:
                    response.headers["Content-Length"] = upstream_resp.headers["Content-Length"]
                if "Content-Range" in upstream_resp.headers:
                    response.headers["Content-Range"] = upstream_resp.headers["Content-Range"]

                await response.prepare(request)

                async for chunk in upstream_resp.content.iter_chunked(64 * 1024):
                    await response.write(chunk)

                await response.write_eof()
                return response
        except Exception as err:
            _LOGGER.error("Error proxying audio stream for %s: %s", video_id, err)
            return web.Response(status=502, text=f"Failed to stream audio: {err}")
