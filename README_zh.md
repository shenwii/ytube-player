<p align="center">
  <img src="custom_components/ytube_player/brand/logo.png" alt="YouTube Player Logo" width="480">
</p>

# YouTube Player for Home Assistant

[English](README.md) | [中文](README_zh.md) | [日本語](README_ja.md)

基于 [yt-dlp](https://github.com/yt-dlp/yt-dlp) 开发的 Home Assistant **YouTube Media Source（媒体源）** 自定义插件。

专为在家里用智能音箱（Sonos、HomePod、Chromecast、DLNA 音箱等）收听 YouTube 内容（音乐、播客、访谈、白噪音等）而设计。仅提取纯音频流，采用 **Home Assistant 本地安全流代理** 方式输出，兼顾音质、设备兼容性与隐私安全。

---

## ✨ 核心特性

- **纯音频流提取**：基于 `yt-dlp` 直接提取最高品质的 `m4a`（AAC）或 `opus` 音频流，无需下载或转码完整视频文件。
- **本地安全流代理（HA Proxy Stream）**：由 Home Assistant 代理转发音频流（`/api/ytube_player/stream/{video_id}`），上游请求携带用户配置的 Cookies 与认证信息，下游仅向音箱输出标准无鉴权的纯音频流。
  - **安全性**：敏感的 YouTube Cookies 绝不向音箱等局域网客户端泄露。
  - **极致兼容**：彻底解决音箱设备无法附加 Cookie/Header、访问 YouTube CDN 报 403 Forbidden 或局域网外网隔离的问题。
  - **智能缓存**：内置音频流解析结果内存缓存，智能音箱快速试探（HEAD/Range 切片）秒起播。
- **媒体浏览器关键词搜索**：在 Home Assistant 的「媒体浏览器（Media Browser）」中直接使用搜索栏查找 YouTube 视频并点击播放。
- **直搜即播（自动化 / 语音助手）**：支持使用关键词直接触发播放，自动检索并播放首条匹配内容（例如：`media-source://ytube_player/search?q=周杰伦`）。
- **自定义 Cookies 支持**：支持在插件设置界面直接粘贴 YouTube Cookie（支持 `SEARCH_SAMESITE=...;` 字符串、标准请求头或 Netscape 文本），轻松规避 YouTube 人机验证（Bot Check）并支持收听会员与受限内容。

---

## 📦 安装方法

### 方法一：手动安装
1. 将本项目中的 `custom_components/ytube_player` 文件夹复制到你的 Home Assistant 配置目录中的 `custom_components` 目录下：
   ```text
   /config/custom_components/ytube_player/
   ```
2. 重启 Home Assistant。

### 方法二：通过 HACS 安装
1. 打开 HACS -> **Integrations（集成）** -> 右上角菜单 -> **Custom repositories（自定义存储库）**。
2. 输入本仓库地址，类别选择 **Integration**。
3. 点击安装后重启 Home Assistant。

---

## ⚙️ 配置说明

1. 在 Home Assistant 中进入 **设置（Settings）** -> **设备与服务（Devices & Services）**。
2. 点击右下角 **添加集成（Add Integration）**，搜索 **`YouTube Player`**。
3. 根据需要填入配置：
   - **YouTube Cookies**（可选）：直接粘贴浏览器的 Cookie 字符串（形如 `SEARCH_SAMESITE=CgQIoqIB; VISITOR_INFO1_LIVE=...` 或带 `cookie:` 前缀的完整 Header）。
4. 点击提交完成配置。后续可在集成的「**选项（Options）**」中随时更新 Cookies 或调整最大搜索结果数，无需重启系统。

---

## 🎵 使用指南

### 1. 在媒体浏览器（Media Browser）中使用
1. 打开 Home Assistant 左侧侧边栏的 **媒体（Media）**。
2. 点击 **YouTube** 进入。
3. 点击顶部的 **搜索（Search）图标**，输入想要收听的歌手、歌曲或播客名称。
4. 在搜索结果列表中选择想要播放的设备，直接点击条目即可开始播放。

### 2. 在自动化或脚本中使用（服务调用）

你可以通过 `media_player.play_media` 动作，指定播放设备和音频内容：

#### 场景 A：根据关键词自动播放第一个搜索结果
```yaml
action: media_player.play_media
target:
  entity_id: media_player.living_room_speaker
data:
  media_content_id: "media-source://ytube_player/search?q=周杰伦 晴天"
  media_content_type: music
```

或者使用路径格式：
```yaml
action: media_player.play_media
target:
  entity_id: media_player.living_room_speaker
data:
  media_content_id: "media-source://ytube_player/search/Lofi Hip Hop Radio"
  media_content_type: music
```

#### 场景 B：通过 YouTube 视频 ID 播放
```yaml
action: media_player.play_media
target:
  entity_id: media_player.living_room_speaker
data:
  media_content_id: "media-source://ytube_player/dQw4w9WgXcQ"
  media_content_type: music
```

#### 场景 C：通过完整 YouTube 网址播放
```yaml
action: media_player.play_media
target:
  entity_id: media_player.living_room_speaker
data:
  media_content_id: "media-source://ytube_player/https://www.youtube.com/watch?v=dQw4w9WgXcQ"
  media_content_type: music
```

---

## 🍪 如何获取 YouTube Cookies

1. 在电脑浏览器（如 Chrome / Edge / Firefox）上打开 [YouTube](https://www.youtube.com) 并登录账号。
2. 按 `F12` 打开开发者工具，切换到 **网络（Network）** 标签页。
3. 刷新页面，点击任意一个对 `youtube.com` 的网络请求。
4. 在右侧 **请求标头（Request Headers）** 中找到 `Cookie:` 字段。
5. 复制该值（例如 `SEARCH_SAMESITE=CgQIoqIB; ...`），粘贴到本插件的 Cookies 设置框中即可。
*(提示：使用 Chrome 扩展如 "Get cookies.txt LOCALLY" 导出的 Netscape 格式文本同样支持直接粘贴。)*

---

## 📄 开源许可

本项目遵循 GPL-3.0 开源许可协议。
