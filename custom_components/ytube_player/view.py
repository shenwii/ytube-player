"""HTTP View for proxying YouTube audio streams to media players."""

from __future__ import annotations

import asyncio
import logging
import os
import re
import shutil
import sys
import time
from typing import Any

from aiohttp import web
from homeassistant.components.http import HomeAssistantView
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import yt_dlp

from .const import CONF_AUDIO_FORMAT, CONF_COOKIES, DEFAULT_AUDIO_FORMAT, DOMAIN
from .cookie_helper import get_ydl_cookie_opts

_LOGGER = logging.getLogger(__name__)

# In-memory cache for resolved stream info: video_id -> (expire_time, info_dict)
_STREAM_CACHE: dict[str, tuple[float, dict[str, Any]]] = {}
_DOWNLOAD_LOCKS: dict[str, asyncio.Lock] = {}
CACHE_TTL = 900  # 15 minutes
MAX_CACHED_FILES = 10
AUDIO_EXTS = (".m4a", ".mp3", ".webm", ".mp4", ".ogg", ".opus")
JSLESS_CLIENTS = ["visionos"]


def _find_node_binary() -> str | None:
    """Locate a Node.js executable from PATH, venv, or nodejs-wheel."""
    for candidate in (
        shutil.which("node"),
        os.path.join(os.path.dirname(sys.executable), "node"),
    ):
        if candidate and os.path.isfile(candidate):
            return candidate

    try:
        import nodejs_wheel  # type: ignore[import-not-found]
    except ImportError:
        return None

    wheel_dir = os.path.dirname(nodejs_wheel.__file__)
    for rel_path in (os.path.join("bin", "node"), "node", "node.exe"):
        candidate = os.path.join(wheel_dir, rel_path)
        if os.path.isfile(candidate):
            return candidate
    return None


def _get_js_runtime_opts() -> dict[str, dict[str, str]]:
    """Build yt-dlp js_runtimes config from available JS executables."""
    runtimes: dict[str, dict[str, str]] = {}
    if deno_path := shutil.which("deno"):
        runtimes["deno"] = {"path": deno_path}
    if node_path := _find_node_binary():
        runtimes["node"] = {"path": node_path}
    if qjs_path := shutil.which("qjs"):
        runtimes["quickjs"] = {"path": qjs_path}
    return runtimes


def clear_stream_cache() -> None:
    """Clear the in-memory stream URL cache."""
    _STREAM_CACHE.clear()


class _YtdlpLogger:
    """Route yt-dlp log messages to Home Assistant logger."""

    def debug(self, msg: str) -> None:
        if msg.startswith("[debug] "):
            _LOGGER.debug("yt-dlp: %s", msg)

    def warning(self, msg: str) -> None:
        _LOGGER.warning("yt-dlp warning: %s", msg)

    def error(self, msg: str) -> None:
        _LOGGER.error("yt-dlp error: %s", msg)


def _mime_for_ext(ext: str | None) -> str:
    """Return an audio/* MIME type for a given file extension."""
    ext_clean = (ext or "m4a").lstrip(".").lower()
    if ext_clean == "mp3":
        return "audio/mpeg"
    if ext_clean in ("webm", "opus"):
        return "audio/webm"
    if ext_clean in ("ogg", "oga"):
        return "audio/ogg"
    return "audio/mp4"


def _get_cache_dir(hass: HomeAssistant) -> str:
    """Return path to the temporary audio cache directory."""
    return hass.config.path(".storage", "ytube_player_cache")


def _find_cached_file(cache_dir: str, video_id: str) -> tuple[str, str] | None:
    """Return (file_path, ext) if a non-empty cached audio file exists."""
    for ext in AUDIO_EXTS:
        candidate = os.path.join(cache_dir, f"{video_id}{ext}")
        if os.path.isfile(candidate) and os.path.getsize(candidate) > 0:
            return candidate, ext
    return None


def _cleanup_cache(cache_dir: str, max_files: int = MAX_CACHED_FILES) -> None:
    """Remove stale .part files and prune older cached audio files."""
    if not os.path.isdir(cache_dir):
        return
    entries: list[tuple[float, str]] = []
    for name in os.listdir(cache_dir):
        full_path = os.path.join(cache_dir, name)
        if not os.path.isfile(full_path):
            continue
        if name.endswith(".part") or name.endswith(".ytdl"):
            try:
                if time.time() - os.path.getmtime(full_path) > 300:
                    os.remove(full_path)
            except OSError:
                pass
            continue
        try:
            entries.append((os.path.getmtime(full_path), full_path))
        except OSError:
            pass

    if len(entries) > max_files:
        entries.sort(reverse=True)
        for _, old_path in entries[max_files:]:
            try:
                os.remove(old_path)
            except OSError:
                pass


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
        for ext in AUDIO_EXTS:
            if cleaned.endswith(ext):
                return cleaned[: -len(ext)]
        return cleaned

    def _get_entry_config(self) -> tuple[str | None, str]:
        """Get configured cookies and audio format."""
        domain_data = self.hass.data.get(DOMAIN, {})
        entry_data: dict[str, Any] = {}
        for entry in domain_data.values():
            if isinstance(entry, dict):
                entry_data = entry
                break
        cookie_str = entry_data.get(CONF_COOKIES)
        audio_format = entry_data.get(CONF_AUDIO_FORMAT, DEFAULT_AUDIO_FORMAT)
        return cookie_str, audio_format

    async def head(self, request: web.Request, video_id: str) -> web.Response:
        """Handle pre-flight HEAD requests from smart speakers like Sonos."""
        clean_id = self._clean_video_id(video_id)
        cache_dir = _get_cache_dir(self.hass)
        cached = await self.hass.async_add_executor_job(_find_cached_file, cache_dir, clean_id)
        headers = {
            "Content-Type": _mime_for_ext(cached[1]) if cached else "audio/mp4",
            "Accept-Ranges": "bytes",
        }
        if cached:
            headers["Content-Length"] = str(os.path.getsize(cached[0]))
        return web.Response(status=200, headers=headers)

    def _build_ydl_opts(
        self,
        cookie_str: str | None,
        audio_format: str,
        *,
        use_cookies: bool,
        player_clients: list[str] | None,
        extra_opts: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Assemble common yt-dlp options including cookies, clients, and JS runtime."""
        ydl_opts: dict[str, Any] = {
            "quiet": True,
            "no_warnings": False,
            "logger": _YtdlpLogger(),
            "format": audio_format,
            "noplaylist": True,
        }
        if js_runtimes := _get_js_runtime_opts():
            ydl_opts["js_runtimes"] = js_runtimes
        if use_cookies and cookie_str:
            ydl_opts.update(get_ydl_cookie_opts(self.hass, cookie_str))
        if player_clients:
            ydl_opts["extractor_args"] = {"youtube": {"player_client": player_clients}}
        if extra_opts:
            ydl_opts.update(extra_opts)
        return ydl_opts

    async def _extract_info(
        self,
        video_id: str,
        cookie_str: str | None,
        audio_format: str,
        *,
        use_cookies: bool = True,
        player_clients: list[str] | None = None,
    ) -> dict[str, Any] | None:
        """Extract stream info using yt-dlp."""
        def _extract() -> dict[str, Any] | None:
            ydl_opts = self._build_ydl_opts(
                cookie_str,
                audio_format,
                use_cookies=use_cookies,
                player_clients=player_clients,
                extra_opts={"skip_download": True},
            )

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                try:
                    return ydl.extract_info(
                        f"https://www.youtube.com/watch?v={video_id}",
                        download=False,
                    )
                except Exception as err:
                    _LOGGER.warning(
                        "yt-dlp extraction failed for %s (cookies=%s, clients=%s): %s",
                        video_id,
                        use_cookies,
                        player_clients,
                        err,
                    )
                    return None

        return await self.hass.async_add_executor_job(_extract)

    async def _try_stream_upstream(
        self,
        request: web.Request,
        video_id: str,
        info: dict[str, Any],
    ) -> web.StreamResponse | None:
        """Attempt to stream a direct HTTP(S) media URL through aiohttp."""
        direct_url = info.get("url")
        protocol = info.get("protocol", "")
        if not direct_url or protocol not in ("http", "https"):
            _LOGGER.debug(
                "Skipping direct stream for %s: protocol=%s", video_id, protocol
            )
            return None

        mime_type = _mime_for_ext(info.get("ext"))

        # Use yt-dlp's own headers + Accept-Encoding: identity; do NOT leak .youtube.com cookies to googlevideo.com
        upstream_headers: dict[str, str] = {"Accept-Encoding": "identity"}
        if info.get("http_headers"):
            upstream_headers.update(info["http_headers"])

        if "range" in request.headers:
            upstream_headers["Range"] = request.headers["range"]

        session = async_get_clientsession(self.hass)
        try:
            async with session.get(direct_url, headers=upstream_headers) as upstream_resp:
                if upstream_resp.status >= 400:
                    _LOGGER.warning(
                        "Upstream YouTube CDN returned HTTP %s for %s (format=%s, protocol=%s)",
                        upstream_resp.status,
                        video_id,
                        info.get("format_id"),
                        protocol,
                    )
                    return None

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
            _LOGGER.warning("Upstream stream error for %s: %s", video_id, err)
            return None

    async def _download_with_ytdlp(
        self,
        video_id: str,
        cookie_str: str | None,
        audio_format: str,
    ) -> tuple[str, str] | None:
        """Download audio track using yt-dlp native downloader to local cache."""
        lock = _DOWNLOAD_LOCKS.setdefault(video_id, asyncio.Lock())
        async with lock:
            cache_dir = _get_cache_dir(self.hass)
            cached = await self.hass.async_add_executor_job(_find_cached_file, cache_dir, video_id)
            if cached:
                return cached

            def _run_download(use_cookies: bool, player_clients: list[str] | None) -> tuple[str, str] | None:
                os.makedirs(cache_dir, exist_ok=True)
                _cleanup_cache(cache_dir)
                outtmpl = os.path.join(cache_dir, f"{video_id}.%(ext)s")
                ydl_opts = self._build_ydl_opts(
                    cookie_str,
                    audio_format,
                    use_cookies=use_cookies,
                    player_clients=player_clients,
                    extra_opts={"outtmpl": outtmpl, "overwrites": True},
                )

                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    try:
                        ydl.download([f"https://www.youtube.com/watch?v={video_id}"])
                        return _find_cached_file(cache_dir, video_id)
                    except Exception as err:
                        _LOGGER.warning(
                            "yt-dlp download failed for %s (cookies=%s, clients=%s): %s",
                            video_id,
                            use_cookies,
                            player_clients,
                            err,
                        )
                        return None

            # Try with configured cookies first, then fallback to JS-less clients without cookies
            attempts: list[tuple[bool, list[str] | None]] = []
            if cookie_str:
                attempts.append((True, None))
            attempts.append((False, None))
            attempts.append((False, JSLESS_CLIENTS))

            for use_cookies, clients in attempts:
                result = await self.hass.async_add_executor_job(
                    _run_download, use_cookies, clients
                )
                if result:
                    return result

            return None

    async def get(self, request: web.Request, video_id: str) -> web.StreamResponse:
        """Stream the audio for the given video_id."""
        if not video_id:
            return web.Response(status=400, text="Missing video_id")

        video_id = self._clean_video_id(video_id)
        if not re.match(r"^[a-zA-Z0-9_-]{1,64}$", video_id):
            return web.Response(status=400, text="Invalid video_id")

        # 1. Serve immediately if already cached locally
        cache_dir = _get_cache_dir(self.hass)
        cached_file = await self.hass.async_add_executor_job(_find_cached_file, cache_dir, video_id)
        if cached_file:
            file_path, ext = cached_file
            return web.FileResponse(
                file_path,
                headers={"Content-Type": _mime_for_ext(ext)},
            )

        cookie_str, audio_format = self._get_entry_config()

        # 2. Try direct streaming with cached or freshly extracted info
        now = time.time()
        cached_info = _STREAM_CACHE.get(video_id)
        info = cached_info[1] if cached_info and cached_info[0] > now else None

        if not info:
            info = await self._extract_info(
                video_id, cookie_str, audio_format, use_cookies=bool(cookie_str)
            )
            if info:
                _STREAM_CACHE[video_id] = (now + CACHE_TTL, info)

        if info:
            streamed = await self._try_stream_upstream(request, video_id, info)
            if streamed is not None:
                return streamed
            # Cached URL failed (e.g. 403 or non-https); invalidate cache
            _STREAM_CACHE.pop(video_id, None)

        # 3. Retry direct streaming with JS-less clients without cookies (avoids missing JS runtime 403)
        fallback_info = await self._extract_info(
            video_id,
            cookie_str,
            audio_format,
            use_cookies=False,
            player_clients=JSLESS_CLIENTS,
        )
        if fallback_info:
            streamed = await self._try_stream_upstream(request, video_id, fallback_info)
            if streamed is not None:
                _STREAM_CACHE[video_id] = (now + CACHE_TTL, fallback_info)
                return streamed

        # 4. Fallback to yt-dlp native download (handles HLS/DASH/retries) and serve FileResponse
        downloaded = await self._download_with_ytdlp(video_id, cookie_str, audio_format)
        if downloaded:
            file_path, ext = downloaded
            return web.FileResponse(
                file_path,
                headers={"Content-Type": _mime_for_ext(ext)},
            )

        _LOGGER.error("All attempts to stream or download YouTube audio failed for %s", video_id)
        return web.Response(status=502, text="Could not stream or download audio from YouTube")
