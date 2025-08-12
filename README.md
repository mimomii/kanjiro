# 幹事郎 - Slack幹事AIエージェント

## 📌 概要
Slack 上で動作するシンプルな幹事ボットです。チャンネルでボットをメンションすると、Hot Pepper グルメ API を使って周辺のお店を検索し、Gemini を用いた LLM が簡潔なおすすめコメントを返します。

## 📁 ディレクトリ構成
```
kanjiro/
├── Dockerfile
├── app/
│   ├── agent/
│   │   ├── __init__.py
│   │   └── llm_agent.py
│   ├── services/
│   │   └── hotpepper.py
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

## 💬 Slack での動作
- チャンネルでボットをメンションし、エリアやジャンルなど検索キーワードを送ると、上位のお店候補とおすすめコメントを返します。
- DM には応答しません。
- チャンネルごとに会話コンテキストを保持し、`ConversationBufferMemory` とローリング要約を併用して長い対話も処理します。

## 🔌 Hot Pepper API キーの取得
`HOTPEPPER_API_KEY` は [Hot Pepper グルメ API](https://webservice.recruit.co.jp/) から発行できます。無料の会員登録後、アプリケーションを登録して取得したキーを `.env` または環境変数に設定してください。

## 🔜 今後の予定
- [ ] Slack メッセージの分類 → 担当エージェント自動割当
- [ ] Webhook 対応（FastAPI 導入）
- [ ] Docker コンテナ実行対応
