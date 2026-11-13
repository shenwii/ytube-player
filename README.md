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
- **Custom Cookies Support**: Easily paste YouTube cookies in integration settings (raw `key=val;` string, HTTP header, or Netscape format) to bypass bot verification and access age-restricted or membership content.

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
3. Fill in the optional settings:
   - **YouTube Cookies** (Optional): Paste your browser cookie string (e.g., `SEARCH_SAMESITE=CgQIoqIB; ...`).
4. Click Submit. You can update cookies or adjust max search results at any time via the integration's **Configure / Options** menu without restarting HA.

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

---

## 🍪 How to Obtain YouTube Cookies

1. In a desktop browser (Chrome, Edge, Firefox, etc.), open [YouTube](https://www.youtube.com) and log in to your account.
2. Press `F12` to open Developer Tools and switch to the **Network** tab.
3. Refresh the page and click on any network request made to `youtube.com`.
4. In the **Request Headers** section on the right, find the `Cookie:` entry.
5. Copy its value (e.g. `SEARCH_SAMESITE=CgQIoqIB; ...`) and paste it into this integration's Cookies field.
*(Note: Netscape-formatted text exported from browser extensions such as "Get cookies.txt LOCALLY" is also supported).*

---

## 📄 License

This project is licensed under the GPL-3.0 License.
