# Kanjiro Minimal Slack App

Slack Bolt(Socket Mode) と FastAPI を併用し、Gemini を利用した会話エージェントと要約エージェントを提供する最小構成です。各ターンで会話要約を更新・保存し、その要約を基に返信を生成します。

## ディレクトリ構成

```
project_root/
├─ main.py
├─ .env
├─ requirements.txt
├─ data/
├─ app/
│  ├─ __init__.py
│  ├─ agent/
│  │  ├─ __init__.py
│  │  └─ llm_agent.py
│  └─ storage/
│     ├─ __init__.py
│     └─ dao.py
```

## 環境変数 (.env)

```ini
SLACK_BOT_TOKEN=xoxb-...
SLACK_APP_TOKEN=xapp-...

# 要約エージェント
GEMINI_API_KEY_SUM=AIza...sum
GEMINI_MODEL_SUM=gemini-1.5-flash

# 会話エージェント
GEMINI_API_KEY_CONV=AIza...conv
GEMINI_MODEL_CONV=gemini-1.5-pro

DB_PATH=./data/kanjiro.sqlite3
PORT=8000
```

## セットアップ & 起動

```bash
pip install -r requirements.txt
python main.py
```

Slack Socket Mode で接続し、FastAPI は `http://localhost:8000/health` でヘルスチェックできます。

## API

- `GET /health` : 稼働確認
- `GET /conversations/{conv_id}/summary/latest` : 指定会話の最新要約を取得

## 動作

- SlackでのメンションまたはDMを受け取ると、要約を更新してSQLiteに保存し、要約に基づいて返信します。
- 要約は `summaries` テーブルでバージョン管理され、同一入力の場合は再登録しません。
