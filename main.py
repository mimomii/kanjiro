"""Slack最小構成 + 受動インジェスト + 幹事フロー登録（参加可否→日付→希望→提案）
※ インメモリ版（再起動で消えます）
"""

import os
import sys
from dotenv import load_dotenv
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

from app.agent.llmajent import LLMAgent  # ← 既存どおり
from app.flows.kanji_flow import register_kanji_flow  # ← 変更後: 第3引数 bot_user_id を渡す

load_dotenv()

REQUIRED_ENV = [
    "SLACK_BOT_TOKEN",
    "SLACK_APP_TOKEN",
    "GEMINI_API_KEY_MAIN",
    "GEMINI_API_KEY_SUMMARY",
]
missing = [k for k in REQUIRED_ENV if not os.environ.get(k)]
if missing:
    sys.stderr.write(f"[ERROR] Missing environment variables: {', '.join(missing)}\n")
    sys.exit(1)

app = App(token=os.environ["SLACK_BOT_TOKEN"])
llm = LLMAgent()  # 日本語で答えるデフォルト設定
BOT_USER_ID = None  # 起動時に auth.test で解決


def _strip_mention(text: str) -> str:
    if not text:
        return ""
    if text.startswith("<@"):
        after = text.split(">", 1)
        return after[1].strip() if len(after) == 2 else text
    return text


@app.event("app_mention")
def on_mention(event, say, logger):
    user = event.get("user")
    prompt = _strip_mention(event.get("text", ""))
    reply = llm.respond(prompt)
    say(text=f"<@{user}> {reply}", thread_ts=event.get("ts"))


# 受動インジェスト：通常メッセージもメモリへ蓄積（返信はしない）
@app.event("message")
def on_message(event, logger):
    if event.get("subtype"):
        return
    user = event.get("user")
    if not user or user == BOT_USER_ID:
        return
    text = _strip_mention(event.get("text", ""))
    if not text:
        return
    llm.remember(f"<@{user}>: {text}")


if __name__ == "__main__":
    # BotユーザーID
    try:
        auth = app.client.auth_test()
        BOT_USER_ID = auth["user_id"]
    except Exception as e:
        sys.stderr.write(f"[WARN] auth_test failed: {e}\n")

    # 幹事フローを登録（Bot ID を渡す）
    register_kanji_flow(app, llm, BOT_USER_ID)

    handler = SocketModeHandler(app, os.environ["SLACK_APP_TOKEN"])
    handler.start()
