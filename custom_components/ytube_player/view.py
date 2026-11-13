"""HTTP View for serving cached YouTube audio streams to media players."""

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
import yt_dlp

from .const import CONF_AUDIO_FORMAT, CONF_COOKIES, DEFAULT_AUDIO_FORMAT, DOMAIN
from .cookie_helper import get_ydl_cookie_opts

_LOGGER = logging.getLogger(__name__)

_DOWNLOAD_LOCKS: dict[str, asyncio.Lock] = {}
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


def _log_runtime_diagnostics(video_id: str) -> None:
    """Log yt-dlp environment details when download attempts fail."""
    yt_dlp_ver = getattr(getattr(yt_dlp, "version", None), "__version__", "unknown")
    try:
        import yt_dlp.dependencies as ydl_deps

        ejs_mod = getattr(ydl_deps, "yt_dlp_ejs", None)
        ejs_ver = getattr(ejs_mod, "__version__", bool(ejs_mod))
    except Exception:
        ejs_ver = "unknown"
    _LOGGER.error(
        "All attempts to download YouTube audio failed for %s "
        "(yt-dlp=%s, ejs=%s, js_runtimes=%s, ffmpeg=%s)",
        video_id,
        yt_dlp_ver,
        ejs_ver,
        _get_js_runtime_opts(),
        shutil.which("ffmpeg"),
    )


def clear_stream_cache() -> None:
    """Lifecycle hook kept for entry reload compatibility."""


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


def _get_entry_config(hass: HomeAssistant) -> tuple[str | None, str]:
    """Get configured cookies and audio format from hass.data."""
    domain_data = hass.data.get(DOMAIN, {})
    entry_data: dict[str, Any] = {}
    for entry in domain_data.values():
        if isinstance(entry, dict):
            entry_data = entry
            break
    cookie_str = entry_data.get(CONF_COOKIES)
    audio_format = entry_data.get(CONF_AUDIO_FORMAT, DEFAULT_AUDIO_FORMAT)
    return cookie_str, audio_format


def _build_ydl_opts(
    hass: HomeAssistant,
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
        "remote_components": ["ejs:github"],
    }
    if js_runtimes := _get_js_runtime_opts():
        ydl_opts["js_runtimes"] = js_runtimes
    if use_cookies and cookie_str:
        ydl_opts.update(get_ydl_cookie_opts(hass, cookie_str))
    if player_clients:
        ydl_opts["extractor_args"] = {"youtube": {"player_client": player_clients}}
    if extra_opts:
        ydl_opts.update(extra_opts)
    return ydl_opts


async def async_ensure_audio_cached(
    hass: HomeAssistant,
    video_id: str,
) -> tuple[str, str] | None:
    """Download and cache the audio file for video_id using yt-dlp if not already cached."""
    cache_dir = _get_cache_dir(hass)
    cached = await hass.async_add_executor_job(_find_cached_file, cache_dir, video_id)
    if cached:
        return cached

    lock = _DOWNLOAD_LOCKS.setdefault(video_id, asyncio.Lock())
    async with lock:
        cached = await hass.async_add_executor_job(_find_cached_file, cache_dir, video_id)
        if cached:
            return cached

        cookie_str, audio_format = _get_entry_config(hass)

        def _run_download(
            use_cookies: bool,
            player_clients: list[str] | None,
            fmt: str,
            postprocessors: list[dict[str, str]] | None,
        ) -> tuple[str, str] | None:
            os.makedirs(cache_dir, exist_ok=True)
            _cleanup_cache(cache_dir)
            outtmpl = os.path.join(cache_dir, f"{video_id}.%(ext)s")
            extra_opts: dict[str, Any] = {"outtmpl": outtmpl, "overwrites": True}
            if postprocessors:
                extra_opts["postprocessors"] = postprocessors
            ydl_opts = _build_ydl_opts(
                hass,
                cookie_str,
                fmt,
                use_cookies=use_cookies,
                player_clients=player_clients,
                extra_opts=extra_opts,
            )

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                try:
                    ydl.download([f"https://www.youtube.com/watch?v={video_id}"])
                    return _find_cached_file(cache_dir, video_id)
                except Exception as err:
                    _LOGGER.warning(
                        "yt-dlp download failed for %s (cookies=%s, clients=%s, format=%s): %s",
                        video_id,
                        use_cookies,
                        player_clients,
                        fmt,
                        err,
                    )
                    return None

        has_ffmpeg = bool(shutil.which("ffmpeg"))
        m4a_pp = (
            [{"key": "FFmpegExtractAudio", "preferredcodec": "m4a"}]
            if has_ffmpeg
            else None
        )
        # Prefer JS-less public client first to avoid logged-in PO Token 403s on normal videos;
        # fall back to default unauthenticated clients, cookies (for restricted/member videos),
        # and ffmpeg transcoding.
        attempts: list[tuple[bool, list[str] | None, str, list[dict[str, str]] | None]] = [
            (False, JSLESS_CLIENTS, audio_format, None),
            (False, None, audio_format, None),
        ]
        if cookie_str:
            attempts.append((True, None, audio_format, None))
        if has_ffmpeg and audio_format != "bestaudio/best":
            attempts.append((False, JSLESS_CLIENTS, "bestaudio/best", m4a_pp))
            if cookie_str:
                attempts.append((True, None, "bestaudio/best", m4a_pp))

        for use_cookies, clients, fmt, postprocessors in attempts:
            result = await hass.async_add_executor_job(
                _run_download, use_cookies, clients, fmt, postprocessors
            )
            if result:
                return result

        return None


class YouTubeStreamView(HomeAssistantView):
    """View to serve locally cached YouTube audio streams."""

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

    async def get(self, request: web.Request, video_id: str) -> web.StreamResponse:
        """Serve the audio for the given video_id."""
        if not video_id:
            return web.Response(status=400, text="Missing video_id")

        video_id = self._clean_video_id(video_id)
        if not re.match(r"^[a-zA-Z0-9_-]{1,64}$", video_id):
            return web.Response(status=400, text="Invalid video_id")

        cached_file = await async_ensure_audio_cached(self.hass, video_id)
        if cached_file:
            file_path, ext = cached_file
            return web.FileResponse(
                file_path,
                headers={"Content-Type": _mime_for_ext(ext)},
            )

        _log_runtime_diagnostics(video_id)
        return web.Response(status=502, text="Could not download audio from YouTube")
