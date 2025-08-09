# 幹事郎 - Slack幹事AIエージェント

## 📌 概要
Slack上で動作する幹事AI「幹事郎」は、飲み会の日程調整・お店探し・空気読みなどを行うマルチエージェントシステムです。

## 📁 ディレクトリ構成

```
kanjiro/
├── Dockerfile
├── app/
│   └── agent/
│       ├── __init__.py
│       ├── base_agent.py
│       ├── hanashi_kikoka.py
│       ├── kennsaku_kennsaku.py
│       ├── llm_agent.py
│       ├── read_air.py
│       └── shikiri_tagari.py
├── main.py
├── requirements.txt
└── .env  (← 手動で作成)
```

## 🛠 セットアップ手順（venv 開発）

1. 仮想環境を作成・有効化：
```bash
cd ~/projects/ai_agents/kanjiro
python3 -m venv .venv
source .venv/bin/activate
```

2. パッケージインストール：
```bash
pip install -r requirements.txt
```

3. `.env` に環境変数を設定：

- SLACK_BOT_TOKEN (ボットトークン)
- SLACK_APP_TOKEN (Socket Mode用)
 - GEMINI_API_KEY
 - GEMINI_MODEL (任意: 使用するモデル名。未指定の場合は`gemini-1.5-flash`)

4. 起動：
```bash
python main.py
```

## 💬 Slackでの動作

- チャンネルでボットをメンションすると **ShikiriTagariAgent** が応答します。
- ボットとのDMでは **HanashiKikokaAgent** が個別にヒアリングします。

## 🤖 実装済みエージェント一覧

| エージェント名 | ファイル | 機能 |
|----------------|----------|------|
| ShikiriTagariAgent | shikiri_tagari.py | 日程調整・仕切り役 |
| ReadAirAgent        | read_air.py | 空気読み |
| HanashiKikokaAgent  | hanashi_kikoka.py | 個人チャットで希望をヒアリング |
| KennsakuKennsakuAgent | kennsaku_kennsaku.py | お店検索・予約候補提示 |
| LLMAgent | llm_agent.py | ベースとなるLLMエージェント |

## 🔜 今後の予定

- [ ] Slackメッセージの分類 → 担当エージェント自動割当
- [ ] Webhook対応（FastAPI導入）
- [ ] Dockerコンテナ実行対応
