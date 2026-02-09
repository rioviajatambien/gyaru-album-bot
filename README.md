# ギャル思い出アルバムBot (Gyaru Memory Album Bot)

LINEで送った旅の写真を、GeminiとPythonが自動で「最高の1枚」に加工してくれるBotです。

## セットアップ手順

### 1. 必要なツールの準備
- Python 3.9以上
- ngrok (ローカルでLINE Botを動かすために必要)
- LINE Developersアカウント
- Google Gemini APIキー

### 2. 環境変数の設定
`.env` ファイルを開き、以下の情報を入力してください。

```bash
CHANNEL_ACCESS_TOKEN=あなたのLINEチャネルアクセストークン
CHANNEL_SECRET=あなたのLINEチャネルシークレット
GEMINI_API_KEY=あなたのGemini APIキー
HOST_URL=https://xxxx-xxxx-xxxx.ngrok-free.app (ngrok起動後に書き換えます)
PORT=8000
```

### 3. 起動方法

1. **ngrokを起動**
   ```bash
   ngrok http 8000
   ```
   表示されたURL (例: `https://xxxx.ngrok-free.app`) をコピーします。

2. **LINE Developers設定**
   - LINE Developersのコンソールで、Webhook URLに `https://xxxx.ngrok-free.app/callback` を設定し、「Webhook利用」をオンにします。

3. **Botを起動**
   ```bash
   # .envのHOST_URLを更新してから実行してください
   python3 app.py
   ```

### 4. 使い方
1. Botに「場所」と「日時」を送る（例：「沖縄, 2024夏」）。
2. Botが「写真を送って！」と言うので、写真を複数枚（5枚以上推奨）送る。
3. 送り終わったら「完了」または「done」と送る。
4. 数秒〜数十秒待つと、加工されたアルバム画像が届きます💖

## 注意点
- **ngrokのURLは毎回変わります**。起動するたびにLINE DevelopersのWebhook URLと`.env`の`HOST_URL`を更新してください。
- 写真は一時的に `tmp/` フォルダに保存されます。
- 生成された画像は `static/images/` に保存されます。
