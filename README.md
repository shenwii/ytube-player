<p align="center">
  <img src="custom_components/ytube_player/brand/logo.png" alt="YouTube Player Logo" width="480">
</p>

# YouTube Player for Home Assistant

[English](README.md) | [中文](README_zh.md) | [日本語](README_ja.md)

A custom Home Assistant **YouTube Media Source** integration powered by [yt-dlp](https://github.com/yt-dlp/yt-dlp).

Designed specifically for listening to YouTube content (music, podcasts, interviews, ambient/white noise, etc.) on smart speakers (Sonos, HomePod, Chromecast, DLNA speakers, etc.) at home. It extracts audio-only streams and serves them through a **Home Assistant local secure proxy**, maximizing audio fidelity, device compatibility, and credential privacy.

---

## ✨ Key Features

- **Pure Audio Extraction**: Leverages `yt-dlp` to directly stream the highest-quality `m4a` (AAC) or `opus` audio without downloading or transcoding full video files.
- **Home Assistant Local Secure Stream Proxy**: Audio streams are safely routed through Home Assistant (`/api/ytube_player/stream/{video_id}`).
  - **Security**: Sensitive YouTube cookies are used strictly between HA and YouTube upstream, never exposed to smart speakers or IoT clients on the LAN.
  - **Universal Compatibility**: Bypasses 403 Forbidden errors caused by smart speakers unable to send cookies/headers to YouTube CDN, and works smoothly across isolated VLANs.
  - **Fast Playback with In-Memory Caching**: Resolves stream URLs with a 15-minute TTL cache, eliminating duplicate lookups when speakers perform initial HEAD/Range byte-probe requests.
- **Search in Media Browser**: Search YouTube directly using the search bar within Home Assistant's Media Browser UI and click to play.
- **Instant Search & Play (Automations & Voice Assistants)**: Trigger playback with raw keywords, automatically extracting and playing the first matching result (e.g., `media-source://ytube_player/search?q=Song Name`).
- **Zero-Config Ready (Optional Cookies)**: Works out of the box with no YouTube login required for most public audio. Optional cookies can still be configured in Options (raw `key=val;` string, HTTP header, or Netscape format) to bypass IP bot checks or access age-restricted/membership content.

---

## 📦 Installation

### Method 1: Manual Installation
1. Copy the `custom_components/ytube_player` directory from this repository into your Home Assistant configuration directory under `custom_components`:
   ```text
   /config/custom_components/ytube_player/
   ```
2. Restart Home Assistant.

### Method 2: Via HACS
1. Open HACS -> **Integrations** -> Top right menu -> **Custom repositories**.
2. Enter this repository URL and select **Integration** as category.
3. Click Install and restart Home Assistant.

---

## ⚙️ Configuration

1. In Home Assistant, go to **Settings** -> **Devices & Services**.
2. Click **Add Integration** in the bottom right corner and search for **`YouTube Player`**.
3. Click **Submit** — no login or cookies are required for normal playback.
4. *(Optional)* If needed later, you can open the integration's **Configure / Options** menu at any time to adjust max search results, audio format selector, or paste YouTube cookies without restarting HA.

---

## 🎵 Usage Guide

### 1. Using the Media Browser UI
1. Navigate to **Media** in the Home Assistant sidebar.
2. Click **YouTube**.
3. Click the **Search** icon in the top bar and enter the artist, song, or podcast title.
4. Select your target media player and click any track from the search results to start playing.

### 2. Using in Automations or Scripts (`media_player.play_media`)

Target any supported media player entity using the `media_player.play_media` action:

#### Case A: Search by keyword and play the first result
```yaml
action: media_player.play_media
target:
  entity_id: media_player.living_room_speaker
data:
  media_content_id: "media-source://ytube_player/search?q=Lofi Hip Hop Radio"
  media_content_type: music
```

Path format is also supported:
```yaml
action: media_player.play_media
target:
  entity_id: media_player.living_room_speaker
data:
  media_content_id: "media-source://ytube_player/search/Lofi Hip Hop Radio"
  media_content_type: music
```

#### Case B: Play via YouTube Video ID
```yaml
action: media_player.play_media
target:
  entity_id: media_player.living_room_speaker
data:
  media_content_id: "media-source://ytube_player/dQw4w9WgXcQ"
  media_content_type: music
```

#### Case C: Play via Full YouTube Video URL
```yaml
action: media_player.play_media
target:
  entity_id: media_player.living_room_speaker
data:
  media_content_id: "media-source://ytube_player/https://www.youtube.com/watch?v=dQw4w9WgXcQ"
  media_content_type: music
```

### 3. Using with MCP / AI Agents

Because `ytube_player` is a `MediaSource` integration (not a `media_player` entity), standard `media_player.search_media` or built-in voice intents will not query it automatically:

- **Direct Search & Play via `media_player.play_media` (Recommended)**:
  Have your MCP client or AI agent call `media_player.play_media` directly on your target speaker with `media_content_id: "media-source://ytube_player/search?q=<keywords>"` and `media_content_type: "music"`. It will automatically search and play the first playable result.
- **Using with Assist / Restricted MCP Toolsets**:
  If your MCP server does not allow passing arbitrary `media_content_id` strings directly, create a Home Assistant Script that calls `media_player.play_media` with `"media-source://ytube_player/search?q={{ query }}"` and expose that script to Assist/MCP.
  *(You can also inspect search results via `media_player.browse_media` with `media_content_id: "media-source://ytube_player/search?q=<keywords>"`.)*

---

## ⚠️ Limitations & Scope

- **Download-Before-Play Buffering Delay**: To ensure reliable playback on smart speakers (such as Sonos, HomePod, and DLNA) that require `Content-Length` and byte-range requests (`Accept-Ranges`), audio is downloaded and cached locally before playback starts. Therefore, the first playback of an uncached item requires waiting for the download to finish (startup time depends on your network speed and audio duration; long videos or podcasts may take noticeable time, while subsequent plays of cached items start immediately).
- **No Live Streams or 24/7 Radios**: Because complete audio files are cached before serving, ongoing live streams, 24/7 radio broadcasts, and upcoming premieres cannot be played and are **automatically excluded from search results** (past live VODs that have already ended are supported).
- **No Playlists or YouTube Mixes**: Playlists, YouTube Mix/Radio collections, and channels are **not supported** and are automatically filtered out from search results. When using instant search & play (`search?q=...`), the integration automatically skips live streams and playlists and plays the first playable single video.
- **Best-Effort Availability (No SLA / High-Availability Guarantee)**: Due to YouTube's rate limiting, anti-bot mechanisms, and upstream changes, this project **does not guarantee high availability or uninterrupted service**. It is designed purely as a lightweight, best-effort solution to meet the bare-minimum need of playing YouTube audio at home.

---

## 🍪 How to Obtain YouTube Cookies *(Optional / Advanced)*

> Most users do **not** need cookies. Only configure this in the integration's **Options** menu if your server IP triggers YouTube bot verification or if you need to play age-restricted / membership-only videos.

1. Install the **Get cookies.txt LOCALLY** browser extension (available for Chrome / Edge, or an equivalent Netscape cookie exporter for Firefox).
2. Open [YouTube](https://www.youtube.com) in your browser and make sure you are logged in.
3. Click the **Get cookies.txt LOCALLY** extension icon and click **Export** (or **Copy**) to copy/download the Netscape-formatted cookies text.
4. Open the text, copy its entire content, and paste it into the **YouTube Cookies** field in this integration's **Options** menu.
*(Note: Raw browser `Cookie:` header strings like `SEARCH_SAMESITE=...;` are also supported).*

---

## 📄 License

This project is licensed under the GPL-3.0 License.
