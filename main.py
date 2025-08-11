"""Slack and FastAPI application with conversation summaries."""

from __future__ import annotations

import os
import sys
import threading
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
import uvicorn
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

from app.agent import SummarizerAgent, ConversationalAgent
from app.storage import (
    init_db,
    get_latest_summary,
    save_new_summary,
    make_input_hash,
)

load_dotenv()

REQUIRED_ENV = [
    "SLACK_BOT_TOKEN",
    "SLACK_APP_TOKEN",
    "GEMINI_API_KEY_SUM",
    "GEMINI_API_KEY_CONV",
]
missing = [k for k in REQUIRED_ENV if not os.environ.get(k)]
if missing:
    sys.stderr.write(f"[ERROR] Missing environment variables: {', '.join(missing)}\n")
    sys.exit(1)

DB_PATH = os.environ.get("DB_PATH", "./data/kanjiro.sqlite3")
PORT = int(os.environ.get("PORT", "8000"))
init_db(DB_PATH)

slack_app = App(token=os.environ["SLACK_BOT_TOKEN"])
summarizer = SummarizerAgent()
conv_agent = ConversationalAgent()

fastapi_app = FastAPI()


@fastapi_app.get("/health")
async def health() -> dict:
    return {"ok": True}


@fastapi_app.get("/conversations/{conv_id}/summary/latest")
async def get_summary_api(conv_id: str) -> dict:
    latest = get_latest_summary(DB_PATH, conv_id)
    if not latest:
        raise HTTPException(status_code=404, detail="summary not found")
    return {"version": latest["version"], "summary_text": latest["text"], "summary_json": latest["json"]}


def _strip_mention(text: str) -> str:
    if not text:
        return ""
    if text.startswith("<@"):
        after = text.split(">", 1)
        return after[1].strip() if len(after) == 2 else text
    return text


def _process_turn(conv_id: str, user_text: str, assistant_last: Optional[str] = None) -> str:
    prev = get_latest_summary(DB_PATH, conv_id)
    input_hash = make_input_hash(prev, user_text, assistant_last)
    summary_text, summary_json = summarizer.summarize(prev, user_text, assistant_last)
    version = save_new_summary(
        DB_PATH,
        conv_id,
        "summarizer",
        summary_text,
        summary_json,
        input_hash,
    )
    reply = conv_agent.reply(
        {"version": version, "text": summary_text, "json": summary_json},
        user_text,
    )
    return reply


@slack_app.event("app_mention")
def on_mention(event, say):
    user = event.get("user")
    prompt = _strip_mention(event.get("text", ""))
    conv_id = f"{event.get('channel')}:{event.get('thread_ts') or 'root'}"
    reply = _process_turn(conv_id, prompt)
    say(f"<@{user}> {reply}", thread_ts=event.get("thread_ts"))


@slack_app.event("message")
def on_dm(event, say):
    if event.get("channel_type") != "im":
        return
    text = event.get("text", "")
    conv_id = f"{event.get('channel')}:{event.get('thread_ts') or 'root'}"
    reply = _process_turn(conv_id, text)
    say(reply, thread_ts=event.get("thread_ts"))


def _run_fastapi() -> None:
    uvicorn.run(fastapi_app, host="0.0.0.0", port=PORT, log_level="info")


if __name__ == "__main__":
    threading.Thread(target=_run_fastapi, daemon=True).start()
    handler = SocketModeHandler(slack_app, os.environ["SLACK_APP_TOKEN"])
    handler.start()
