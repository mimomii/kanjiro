"""Slack でメンションにのみ応答する最小構成。

飲み会の日時や場所、お店の候補を決めるためにチャンネルごとの
会話コンテキストを保持する。"""

import os
import sys
from dotenv import load_dotenv
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

from app.agent.llm_agent import LLMAgent

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
llm = LLMAgent()  # 飲み会幹事用のエージェント


def _strip_mention(text: str) -> str:
    if not text:
        return ""
    # 先頭のメンション (<@UXXXX>) を雑に除去
    if text.startswith("<@"):
        after = text.split(">", 1)
        return after[1].strip() if len(after) == 2 else text
    return text


@app.event("app_mention")
def on_mention(event, say):
    user = event.get("user")
    channel = event.get("channel")
    prompt = _strip_mention(event.get("text", ""))
    reply = llm.respond(prompt, channel)
    say(f"<@{user}> {reply}")


if __name__ == "__main__":
    handler = SocketModeHandler(app, os.environ["SLACK_APP_TOKEN"])
    handler.start()

