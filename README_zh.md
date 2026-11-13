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
- **免登录开箱即用（Cookies 仅作进阶可选项）**：绝大多数公开音频无需登录或配置 Cookies 即可直接搜索与播放；仅在 IP 触发人机验证或需要收听会员/年龄限制内容时，才需在「选项」中粘贴 Cookies（支持 `key=val;` 字符串、请求头或 Netscape 格式）。

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
3. 直接点击 **提交** 即可完成安装，常规使用**无需登录或填写任何 Cookies**。
4. *（可选）* 后续可在集成的「**选项（Options）**」中随时调整最大搜索结果数、音频格式选择器，或按需补充配置 Cookies，无需重启系统。

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

### 3. 在 MCP / AI 助手中使用

由于本插件属于 `MediaSource`（媒体源）而非 `media_player` 实体，Home Assistant 原生的 `media_player.search_media` 或内置语音搜索不会自动查到本插件：

- **通过 `media_player.play_media` 直搜即播（推荐）**：
  只要你的 MCP / AI 助手支持调用 `media_player.play_media`，直接让它对目标音箱传入 `media_content_id: "media-source://ytube_player/search?q=搜索关键词"`、`media_content_type: "music"`，即可自动检索并播放首个可播放结果。
- **通过 HA 脚本（Script）暴露给受限 MCP / Assist**：
  如果你的 MCP 工具集无法直接构造自定义 `media-source://` 参数，可以在 Home Assistant 中新建一个调用上述 `media_player.play_media` 的脚本并暴露给 Assist/MCP。
  *（如支持 `media_player.browse_media`，也可传入 `media_content_id: "media-source://ytube_player/search?q=搜索关键词"` 来浏览候选结果列表。）*

---

## ⚠️ 使用限制与定位说明

- **先下载后播放的缓冲等待**：为了兼顾 Sonos、HomePod、DLNA 等智能音箱的兼容性（需要完整 `Content-Length` 与 `Accept-Ranges` 分片请求支持），本插件会先将音频完整下载到本地缓存后再提供播放。因此首次点击未缓存的视频时，起播速度取决于当前网络速度与音频时长（长视频或长播客首次等待会较明显；已缓存条目再次点击可秒播）。
- **不支持直播流与 24 小时电台**：由于采用先缓存完整文件再播放的方式，正在进行的直播、24 小时电台流及尚未开播的预告无法播放，**搜索结果中已自动排除此类条目**（已结束并转为点播的直播回放仍可正常播放）。
- **不支持播放列表（Playlist）与合辑电台（Mix）**：播放列表、YouTube Mix 合辑电台及频道等非单曲条目**无法直接播放**，搜索结果中已自动过滤。使用自动化「直搜即播（`search?q=...`）」时，也会自动跳过前排的电台与播放列表，播放首个可播放的单条音频。
- **不保证高可用性（仅追求最低限度可用）**：受限于 YouTube 自身的限速、风控、人机验证及上游接口变动等策略，本项目**不保证高可用性或 100% 稳定无故障**，只以“在家庭智能音箱上以最低限度正常播放 YouTube 音频”为目标。

---

## 🍪 如何获取 YouTube Cookies *（可选 / 进阶）*

> 绝大多数用户**无需配置 Cookies**。仅当你所在的服务器 IP 触发了 YouTube 人机验证，或需要播放会员/年龄限制内容时，才需要按下方步骤获取并在集成「**选项**」中填入。

1. 在电脑浏览器（Chrome / Edge）中安装 **Get cookies.txt LOCALLY** 扩展（Firefox 可使用同类 Netscape 格式 Cookie 导出扩展）。
2. 在浏览器中打开 [YouTube](https://www.youtube.com) 并确保已登录账号。
3. 点击浏览器右上角的 **Get cookies.txt LOCALLY** 扩展图标，点击 **Export**（导出）或 **Copy**（复制）获取 Netscape 格式的 Cookies 文本。
4. 全选复制导出的文本内容，打开本集成的「**选项（Options）**」，粘贴到 **YouTube Cookies** 输入框中保存即可。
*(提示：也同样支持直接粘贴浏览器请求头中的 `Cookie:` 字符串。)*

---

## 📄 开源许可

本项目遵循 GPL-3.0 开源许可协议。
