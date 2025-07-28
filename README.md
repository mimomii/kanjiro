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

3.  に環境変数を設定：

- SLACK_BOT_TOKEN
- SLACK_SIGNING_SECRET
- OPENAI_API_KEY

4. 起動：
```bash
python main.py
```

## 🤖 実装済みエージェント一覧

| エージェント名 | ファイル | 機能 |
|----------------|----------|------|
| ShikiriTagariAgent |  | 日程調整・仕切り役 |
| ReadAirAgent        |         | 空気読み |
| HanashiKikokaAgent  |   | 話の要点整理 |
| KennsakuKennsakuAgent |  | お店検索（仮） |

## 🔜 今後の予定

- [ ] OpenAI API 統合による自然言語応答
- [ ] Slackメッセージの分類 → 担当エージェント自動割当
- [ ] Webhook対応（FastAPI導入）
- [ ] Dockerコンテナ実行対応
