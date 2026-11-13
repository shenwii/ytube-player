<p align="center">
  <img src="custom_components/ytube_player/brand/logo.png" alt="YouTube Player Logo" width="480">
</p>

# YouTube Player for Home Assistant

[English](README.md) | [中文](README_zh.md) | [日本語](README_ja.md)

[yt-dlp](https://github.com/yt-dlp/yt-dlp) をベースにした Home Assistant 向け **YouTube Media Source（メディアソース）** カスタムインテグレーションです。

家庭内のスマートスピーカー（Sonos、HomePod、Chromecast、DLNA スピーカーなど）で、YouTube の音声コンテンツ（音楽、ポッドキャスト、対談、環境音など）を高音質かつ手軽に楽しむために設計されています。純粋な音声ストリームのみを抽出し、**Home Assistant ローカルセキュアプロキシ** 経由で配信することで、音質、再生機器との互換性、セキュリティを両立しています。

---

## ✨ 主な機能

- **高音質音声ストリーム抽出**：`yt-dlp` を使用して最高品質の `m4a` (AAC) または `opus` 音声ストリームを直接抽出。動画ファイル全体をダウンロード・変換する必要はありません。
- **Home Assistant ローカルセキュアプロキシ**：Home Assistant が音声ストリームをプロキシ中継（`/api/ytube_player/stream/{video_id}`）します。
  - **高い安全性**：設定されたクッキーは YouTube へのリクエストにのみ使用され、ローカルネットワーク上のスピーカー機器には一切漏洩しません。
  - **抜群の互換性**：スマートスピーカーがクッキー/ヘッダーを送信できずに YouTube CDN から 403 Forbidden で拒絶される問題や、VLAN によるインターネット制限を完全に解消します。
  - **インメモリキャッシュ**：解析結果をメモリにキャッシュするため、スマートスピーカーの事前プローブ（HEAD / Range リクエスト）時にも遅延なく即座に再生が開始されます。
- **メディアブラウザでのキーワード検索**：Home Assistant の「メディアブラウザ」内の検索バーから YouTube 動画を直接検索して選択・再生できます。
- **検索即再生（自動化・音声アシスタント対応）**：キーワードを指定するだけで、検索結果の第1件目を自動抽出して即座に再生（例: `media-source://ytube_player/search?q=曲名やアーティスト`）。
- **カスタムクッキー対応**：インテグレーションの設定画面から YouTube クッキー（`SEARCH_SAMESITE=...;` 形式、リクエストヘッダー、Netscape 形式）を直接貼り付け可能。ボット判定の回避や年齢制限・メンバーシップ限定コンテンツの再生に対応します。

---

## 📦 インストール方法

### 方法1: 手動インストール
1. リポジトリ内の `custom_components/ytube_player` フォルダを、Home Assistant の設定ディレクトリ配下の `custom_components` にコピーします:
   ```text
   /config/custom_components/ytube_player/
   ```
2. Home Assistant を再起動します。

### 方法2: HACS でのインストール
1. HACS -> **インテグレーション** -> 右上のメニュー -> **カスタムリポジトリ** を開きます。
2. 本リポジトリの URL を入力し、カテゴリで **Integration** を選択して追加します。
3. インストール後、Home Assistant を再起動します。

---

## ⚙️ 設定方法

1. Home Assistant の **設定** -> **デバイスとサービス** に移動します。
2. 右下の **統合を追加** をクリックし、**`YouTube Player`** を検索します。
3. 必要に応じて設定を入力します:
   - **YouTube クッキー**（省略可）: ブラウザから取得したクッキー文字列（例: `SEARCH_SAMESITE=CgQIoqIB; ...`）を貼り付けます。
4. 送信をクリックして完了します。後からいつでもインテグレーションの「**オプション**」からクッキーの更新や検索件数の変更が可能です（再起動不要）。

---

## 🎵 使い方

### 1. メディアブラウザでの利用
1. Home Assistant のサイドバーから **メディア** を開きます。
2. **YouTube** を選択します。
3. 画面右上の **検索アイコン** をタップし、再生したい楽曲や番組名を入力します。
4. 検索結果一覧から再生対象のスピーカーを選択し、曲をタップすると再生が始まります。

### 2. 自動化やスクリプトでの利用（サービス呼び出し）

`media_player.play_media` アクションを使用して、対象スピーカーと再生内容を指定できます:

#### パターン A: キーワードで最初の検索結果を自動再生
```yaml
action: media_player.play_media
target:
  entity_id: media_player.living_room_speaker
data:
  media_content_id: "media-source://ytube_player/search?q=YOASOBI アイドル"
  media_content_type: music
```

パス形式での指定も可能です:
```yaml
action: media_player.play_media
target:
  entity_id: media_player.living_room_speaker
data:
  media_content_id: "media-source://ytube_player/search/Lofi Hip Hop Radio"
  media_content_type: music
```

#### パターン B: YouTube 動画 ID で再生
```yaml
action: media_player.play_media
target:
  entity_id: media_player.living_room_speaker
data:
  media_content_id: "media-source://ytube_player/dQw4w9WgXcQ"
  media_content_type: music
```

#### パターン C: YouTube URL で再生
```yaml
action: media_player.play_media
target:
  entity_id: media_player.living_room_speaker
data:
  media_content_id: "media-source://ytube_player/https://www.youtube.com/watch?v=dQw4w9WgXcQ"
  media_content_type: music
```

---

## ⚠️ 制限事項

- **ライブ配信・24時間ラジオには非対応**：Sonos、HomePod、DLNA などのスマートスピーカーが要求する `Content-Length` およびレンジリクエスト（`Accept-Ranges`）に安定して対応するため、本インテグレーションは音声をローカルにダウンロード・キャッシュしてから配信しています。そのため、現在配信中のライブ、24時間ラジオ、公開予定のプレミア配信は再生できず、**検索結果から自動的に除外されます**（配信終了済みのアーカイブ動画は再生可能です）。
- **プレイリスト・YouTube ミックスには非対応**：プレイリスト、YouTube ミックス（ラジオ）、チャンネルなどの複数動画コレクションは**再生対象外**となり、検索結果から自動的にフィルタリングされます。検索即再生（`search?q=...`）利用時も、先頭のライブやプレイリストを自動でスキップし、最初に再生可能な単一動画を再生します。

---

## 🍪 YouTube クッキーの取得方法

1. PC のブラウザ（Chrome / Edge / Firefox など）で [YouTube](https://www.youtube.com) を開き、アカウントにログインします。
2. `F12` キーを押して開発者ツール（デベロッパーツール）を開き、**ネットワーク (Network)** タブに切り替えます。
3. ページを再読み込みし、`youtube.com` への通信リクエストをどれか1つ選択します。
4. 右側の **リクエストヘッダー (Request Headers)** 内にある `Cookie:` の値をコピーします。
5. コピーした値（例: `SEARCH_SAMESITE=CgQIoqIB; ...`）を本インテグレーションの設定欄に貼り付けます。
*(※ Chrome 拡張機能「Get cookies.txt LOCALLY」などでエクスポートした Netscape 形式テキストもそのまま貼り付け可能です)*

---

## 📄 ライセンス

本プロジェクトは GPL-3.0 ライセンスの元で公開されています。
