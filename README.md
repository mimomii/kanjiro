# 幹事郎 - Slack幹事AIエージェント

## 📌 概要
Slack上で動作する幹事AI「幹事郎」は、飲み会の日程調整やお店探しを支援するシンプルなボットです。
グループチャットでメンバーから意見を集め、最終的な日時や場所、お店の候補を提案します。

## 📁 ディレクトリ構成
```
kanjiro/
├── Dockerfile
├── app/
│   ├── agent/
│   │   ├── __init__.py
│   │   └── llm_agent.py
│   └── minimal_context_memory.py
├── main.py
├── requirements.txt
└── .env  (← 手動で作成)
```

## 🛠 セットアップ手順（venv 開発）
1. 仮想環境を作成・有効化：
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```
2. パッケージインストール：
   ```bash
   pip install -r requirements.txt
   ```
3. `.env` に環境変数を設定：
    - `SLACK_BOT_TOKEN`
    - `SLACK_APP_TOKEN`
    - `GEMINI_API_KEY_MAIN`
    - `GEMINI_API_KEY_SUMMARY`
    - `HOTPEPPER_API_KEY`
4. 起動：
   ```bash
   python main.py
   ```

## 💬 Slackでの動作
- チャンネルでボットをメンションすると、**LLMAgent** がメッセージを生成して返信します。
- DM には応答しません。
- チャンネルごとに会話コンテキストを保持し、`ConversationBufferMemory` とローリング要約を併用して長い対話も処理します。

## 📚 会話コンテキストの例
`app/minimal_context_memory.py` は、外部ストレージを使わずに
`ConversationBufferMemory` とローリング要約を組み合わせてコンテキストを
保持する最小サンプルです。Gemini APIキーを2つ用意し、応答生成用と要約専用
に分けています。Slack bot でも同じ仕組みを利用しています。

## 🔌 Hot Pepper API キーの取得
`HOTPEPPER_API_KEY` は [Hot Pepper グルメ API](https://webservice.recruit.co.jp/) から
発行できます。無料の会員登録後、アプリケーションを登録して取得したキーを
`.env` または環境変数に設定してください。

## 🔜 今後の予定
- [ ] Slackメッセージの分類 → 担当エージェント自動割当
- [ ] Webhook対応（FastAPI導入）
- [ ] Dockerコンテナ実行対応
