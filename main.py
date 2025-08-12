"""Slack でメンションにのみ応答する最小構成。

飲み会の日時や場所、お店の候補を決めるためにチャンネルごとの
会話コンテキストを保持する。"""

import os
import sys
from typing import Any, Dict

from dotenv import load_dotenv
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

from app.agent.llm_agent import LLMAgent
from app.models.events import EventContext, ParticipantPref
from app.state.session_store import SessionStore
from app.blocks.shops import shortlist_blocks, shop_to_blocks
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
llm = LLMAgent()  # 飲み会幹事用のエージェント
session_store = SessionStore()


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
    """Handle @bot mentions by launching the modal."""

    user = event.get("user")
    channel = event.get("channel")
    prompt = _strip_mention(event.get("text", ""))
    reply = llm.respond(prompt, channel)
    say(f"<@{user}> {reply}")


@app.command("/幹事")
def command_start(ack, body, client, logger):
    """Slash command entry point to open the organizer modal."""

    ack()
    try:
        view = _build_modal(body.get("channel_id"))
        client.views_open(trigger_id=body["trigger_id"], view=view)
    except Exception as e:  # pragma: no cover - best effort
        logger.exception("modal open failed: %s", e)


def _build_modal(channel_id: str | None) -> Dict[str, Any]:
    """Return a modal for collecting event info."""

    return {
        "type": "modal",
        "callback_id": "event_modal",
        "title": {"type": "plain_text", "text": "幹事設定"},
        "submit": {"type": "plain_text", "text": "送信"},
        "private_metadata": channel_id or "",
        "blocks": [
            {
                "type": "input",
                "block_id": "participants",
                "element": {
                    "type": "multi_users_select",
                    "action_id": "participants_select",
                },
                "label": {"type": "plain_text", "text": "参加者"},
            },
            {
                "type": "input",
                "block_id": "date",
                "element": {
                    "type": "plain_text_input",
                    "action_id": "date_candidates_text",
                    "multiline": True,
                },
                "label": {"type": "plain_text", "text": "日程候補"},
            },
            {
                "type": "input",
                "block_id": "start",
                "element": {
                    "type": "plain_text_input",
                    "action_id": "start_time_range",
                },
                "label": {"type": "plain_text", "text": "開始時刻帯"},
            },
            {
                "type": "input",
                "block_id": "area",
                "element": {
                    "type": "plain_text_input",
                    "action_id": "area_text",
                },
                "label": {"type": "plain_text", "text": "エリア"},
            },
            {
                "type": "input",
                "block_id": "genre",
                "element": {
                    "type": "plain_text_input",
                    "action_id": "genre_candidates_text",
                },
                "label": {"type": "plain_text", "text": "ジャンル候補"},
            },
            {
                "type": "input",
                "optional": True,
                "block_id": "budget",
                "element": {
                    "type": "number_input",
                    "is_decimal_allowed": False,
                    "action_id": "budget_max",
                },
                "label": {"type": "plain_text", "text": "予算上限(円)"},
            },
            {
                "type": "input",
                "block_id": "must",
                "optional": True,
                "element": {
                    "type": "checkboxes",
                    "action_id": "must_haves",
                    "options": [
                        {
                            "text": {"type": "plain_text", "text": "個室"},
                            "value": "private_room",
                        },
                        {
                            "text": {"type": "plain_text", "text": "禁煙"},
                            "value": "non_smoking",
                        },
                        {
                            "text": {"type": "plain_text", "text": "飲み放題"},
                            "value": "free_drink",
                        },
                        {
                            "text": {"type": "plain_text", "text": "コース"},
                            "value": "course",
                        },
                    ],
                },
                "label": {"type": "plain_text", "text": "必須条件"},
            },
        ],
    }


@app.view("event_modal")
def handle_submission(ack, body, view, client, logger):
    """Handle modal submission to create an event context and post survey."""

    ack()
    try:
        state = view["state"]["values"]
        participants = state["participants"]["participants_select"].get(
            "selected_users", []
        )
        date_candidates = (
            state["date"]["date_candidates_text"].get("value", "").splitlines()
        )
        start_time_range = state["start"]["start_time_range"].get("value", "")
        area_text = state["area"]["area_text"].get("value", "")
        genre_candidates = (
            state["genre"]["genre_candidates_text"].get("value", "").split()
        )
        budget_max_raw = state["budget"]["budget_max"].get("value") if "budget" in state else None
        budget_max = int(budget_max_raw) if budget_max_raw else None
        must_haves = {opt["value"]: True for opt in state.get("must", {}).get("must_haves", {}).get("selected_options", [])} if "must" in state else {}

        channel = view.get("private_metadata") or body.get("channel", {}).get("id")
        organizer = body.get("user", {}).get("id")
        ctx = EventContext(
            channel=channel,
            thread_ts="",
            organizer=organizer,
            date_candidates=date_candidates,
            start_time_range=start_time_range,
            area_text=area_text,
            genre_candidates=genre_candidates,
            must_haves=must_haves,
            budget_min=None,
            budget_max=budget_max,
            participants=participants,
        )
        # post survey message
        res = client.chat_postMessage(
            channel=channel,
            text=(
                "参加者アンケート: 🌶=辛いOK, 🐟=海鮮OK, 🚭=禁煙希望, "
                "💬=自由記述はスレッドに返信してください"
            ),
        )
        ctx.thread_ts = res["ts"]
        session_store.set(f"{channel}:{ctx.thread_ts}", ctx)
    except Exception as e:  # pragma: no cover - best effort
        logger.exception("submission handling failed: %s", e)


@app.event("reaction_added")
def handle_reaction(event, logger):
    """Collect simple preferences based on reactions."""

    item = event.get("item", {})
    channel = item.get("channel")
    thread_ts = item.get("thread_ts") or item.get("ts")
    if not channel or not thread_ts:
        return
    session_id = f"{channel}:{thread_ts}"
    ctx = session_store.get(session_id)
    if not ctx:
        return

    user = event.get("user")
    reaction = event.get("reaction")
    pref = ctx.prefs_by_user.get(user, ParticipantPref(user))
    if reaction == "hot_pepper":
        pref.spicy_ok = True
    elif reaction == "fish":
        pref.seafood_ok = True
    ctx.prefs_by_user[user] = pref
    session_store.set(session_id, ctx)


@app.action("add_candidate")
def action_add_candidate(ack, body, client, logger):
    ack()
    try:
        channel = body["channel"]["id"]
        thread_ts = body["message"].get("thread_ts") or body["message"].get("ts")
        session_id = f"{channel}:{thread_ts}"
        ctx = session_store.get(session_id)
        if not ctx:
            return
        shop_id = body["actions"][0]["value"]
        if shop_id not in [s.get("id") for s in ctx.shortlist]:
            ctx.shortlist.append({"id": shop_id})
        session_store.set(session_id, ctx)
        client.chat_postMessage(
            channel=channel, thread_ts=thread_ts, blocks=shortlist_blocks(ctx.shortlist)
        )
    except Exception as e:  # pragma: no cover - best effort
        logger.exception("add candidate failed: %s", e)


@app.action("exclude_candidate")
def action_exclude_candidate(ack, body, client, logger):
    ack()
    try:
        channel = body["channel"]["id"]
        thread_ts = body["message"].get("thread_ts") or body["message"].get("ts")
        session_id = f"{channel}:{thread_ts}"
        ctx = session_store.get(session_id)
        if not ctx:
            return
        shop_id = body["actions"][0]["value"]
        ctx.shortlist = [s for s in ctx.shortlist if s.get("id") != shop_id]
        session_store.set(session_id, ctx)
        client.chat_postMessage(
            channel=channel, thread_ts=thread_ts, blocks=shortlist_blocks(ctx.shortlist)
        )
    except Exception as e:  # pragma: no cover - best effort
        logger.exception("exclude candidate failed: %s", e)


if __name__ == "__main__":
    handler = SocketModeHandler(app, os.environ["SLACK_APP_TOKEN"])
    handler.start()

