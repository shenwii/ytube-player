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
- **ログイン不要ですぐに使える（クッキーは任意の上級設定）**：通常の公開コンテンツはログインやクッキー設定なしで利用できます。IP によるボット判定が出た場合や年齢制限・メンバー限定コンテンツを再生したい場合のみ、「オプション」からクッキー（`key=val;` 文字列、HTTP ヘッダー、Netscape 形式）を設定できます。

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
3. **送信** をクリックするだけでセットアップが完了します。通常の利用では**ログインやクッキーの入力は不要**です。
4. *（任意）* 後からいつでもインテグレーションの「**オプション**」から最大検索件数やオーディオフォーマット指定を変更したり、必要に応じてクッキーを追加設定できます（再起動不要）。

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

### 3. MCP・AI エージェントでの利用

本インテグレーションは `media_player` エンティティではなく `MediaSource`（メディアソース）として動作するため、標準の `media_player.search_media` や音声インテントからは自動検索されません：

- **`media_player.play_media` を使った検索即再生（推奨）**：
  MCP や AI エージェントから `media_player.play_media` を呼び出せる場合は、対象スピーカーに対して `media_content_id` に `"media-source://ytube_player/search?q=検索キーワード"`、`media_content_type` に `"music"` を渡すだけで、最初に再生可能な結果を自動再生します。
- **HA スクリプト経由での公開（ツール制限のある MCP / Assist 向け）**：
  利用中の MCP 側で任意の `media-source://` URI を渡しにくい場合は、上記 `media_player.play_media` を呼び出す Home Assistant スクリプトを作成し、Assist / MCP に公開してください。
  *（`media_player.browse_media` を使う場合は、`media_content_id: "media-source://ytube_player/search?q=検索キーワード"` で検索結果一覧を取得することもできます。）*

---

## ⚠️ 制限事項と位置づけ

- **ダウンロード後の再生による待ち時間**：Sonos、HomePod、DLNA などのスマートスピーカーが要求する `Content-Length` およびレンジリクエスト（`Accept-Ranges`）に安定して対応するため、本インテグレーションは音声ファイルをローカルに完全ダウンロード・キャッシュしてから配信します。そのため未キャッシュの動画を初めて再生する際はダウンロード完了まで待ち時間が発生します（回線速度や動画の長さによって変わり、長尺動画では時間がかかります。キャッシュ済みの動画は即座に再生されます）。
- **ライブ配信・24時間ラジオには非対応**：完全なファイルをキャッシュしてから配信する仕組みのため、現在配信中のライブ、24時間ラジオ、公開予定のプレミア配信は再生できず、**検索結果から自動的に除外されます**（配信終了済みのアーカイブ動画は再生可能です）。
- **プレイリスト・YouTube ミックスには非対応**：プレイリスト、YouTube ミックス（ラジオ）、チャンネルなどの複数動画コレクションは**再生対象外**となり、検索結果から自動的にフィルタリングされます。検索即再生（`search?q=...`）利用時も、先頭のライブやプレイリストを自動でスキップし、最初に再生可能な単一動画を再生します。
- **高可用性の保証なし（最低限の再生を目的）**：YouTube 側の帯域制限、ボット対策、仕様変更などの影響を受けるため、本プロジェクトは**高可用性（HA）や常時安定した動作を保証するものではありません**。自宅のスマートスピーカーで YouTube 音声を「最低限再生できること」を主目的としたベストエフォートの実装です。

---

## 🍪 YouTube クッキーの取得方法 *（任意 / 上級者向け）*

> ほとんどのユーザーは**クッキーの設定不要**です。サーバー IP が YouTube のボット判定に引っかかった場合や、年齢制限・メンバー限定動画を再生したい場合のみ、以下の手順で取得し「**オプション**」に貼り付けてください。

1. PC のブラウザ（Chrome / Edge）に拡張機能 **Get cookies.txt LOCALLY** をインストールします（Firefox の場合は同等の Netscape 形式クッキー出力拡張機能を使用してください）。
2. ブラウザで [YouTube](https://www.youtube.com) を開き、アカウントにログインした状態にします。
3. ブラウザ右上の **Get cookies.txt LOCALLY** アイコンをクリックし、**Export** または **Copy** で Netscape 形式のクッキーテキストを取得します。
4. 出力されたテキストをすべてコピーし、本インテグレーションの「**オプション**」内にある **YouTube クッキー** 欄にそのまま貼り付けて保存します。
*(※ ブラウザのリクエストヘッダーから取得した `Cookie:` 文字列形式の貼り付けにも対応しています)*

---

## 📄 ライセンス

本プロジェクトは GPL-3.0 ライセンスの元で公開されています。
