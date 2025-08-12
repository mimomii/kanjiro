"""Simple Slack bot that proposes restaurants using Hot Pepper Gourmet API."""

import os
import sys
from typing import List

from dotenv import load_dotenv
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

from app.agent.llm_agent import LLMAgent
from app.services.hotpepper import search_shops

load_dotenv()

REQUIRED_ENV = [
    "SLACK_BOT_TOKEN",
    "SLACK_APP_TOKEN",
    "GEMINI_API_KEY_MAIN",
    "GEMINI_API_KEY_SUMMARY",
    "HOTPEPPER_API_KEY",
]
missing = [k for k in REQUIRED_ENV if not os.environ.get(k)]
if missing:
    sys.stderr.write(f"[ERROR] Missing environment variables: {', '.join(missing)}\n")
    sys.exit(1)

app = App(token=os.environ["SLACK_BOT_TOKEN"])
llm = LLMAgent()


def _strip_mention(text: str) -> str:
    if not text:
        return ""
    if text.startswith("<@"):
        after = text.split(">", 1)
        return after[1].strip() if len(after) == 2 else text
    return text


@app.event("app_mention")
def on_mention(event, say, logger):
    """Handle mentions by searching Hot Pepper and replying with suggestions."""

    query = _strip_mention(event.get("text", ""))
    try:
        shops = search_shops(query, [], None, {})
        if not shops:
            say("該当するお店が見つかりませんでした。")
            return
        lines: List[str] = [f"{i+1}. {s['name']} {s['urls']}" for i, s in enumerate(shops[:5])]
        summary = llm.respond(
            "以下のお店候補からおすすめを簡潔に教えて:\n" + "\n".join(lines),
            event.get("channel"),
        )
        say(summary + "\n" + "\n".join(lines))
    except Exception as e:  # pragma: no cover - best effort
        logger.exception("search failed: %s", e)
        say("検索に失敗しました。")


if __name__ == "__main__":
    handler = SocketModeHandler(app, os.environ["SLACK_APP_TOKEN"])
    handler.start()
