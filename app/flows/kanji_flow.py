# app/flows/kanji_flow.py
from __future__ import annotations
import json
from typing import Dict, List
from slack_bolt import App

from app.store import (
    create_plan, upsert_participant, list_participants, record_vote,
    get_latest_plan_thread, eligible_voter_ids, tally_votes, voters_who_voted
)
from app.services.shops import search_shops_api


def _participants_summary(rows) -> Dict:
    import statistics
    from collections import Counter

    yes_users = [r for r in rows if (r.get("attendance") in ("yes", "maybe"))]

    # dates
    cnt_dates = Counter()
    for r in yes_users:
        for d in r.get("dates") or []:
            cnt_dates[d] += 1

    # area: 最頻
    areas = [r.get("area") for r in yes_users if r.get("area")]
    area = Counter(areas).most_common(1)[0][0] if areas else None

    # budget: 中央
    mins = [int(r.get("budget_min")) for r in yes_users if r.get("budget_min") is not None]
    maxs = [int(r.get("budget_max")) for r in yes_users if r.get("budget_max") is not None]
    budget = (
        (int(statistics.median(mins)), int(statistics.median(maxs)))
        if mins and maxs else (3000, 5000)
    )

    # cuisine: 上位3
    cuisines_raw = [r.get("cuisine") for r in yes_users if r.get("cuisine")]
    cuisine_list: List[str] = []
    for c in cuisines_raw:
        cuisine_list.extend([x.strip() for x in c.split(",") if x.strip()])
    top_cuisine = [c for c, _ in Counter(cuisine_list).most_common(3)] if cuisine_list else []

    return {"date_counts": cnt_dates, "area": area, "budget": budget, "cuisine": top_cuisine}


def _pick_top_dates(date_counts, k=3) -> List[str]:
    return [d for d, _ in date_counts.most_common(k)]


def _proposal_blocks(proposals: List[Dict]) -> List[Dict]:
    blocks: List[Dict] = []
    for i, p in enumerate(proposals, start=1):
        shops_md = "\n".join(
            [f"- <{s['url']}|{s['name']}>（{s.get('budget_label','-')}）" for s in p["shops"]]
        ) or "- 候補取得なし"
        header = f"提案{i}：{p['date']} @ {p.get('area','-')}"
        budget_txt = f"¥{p['budget'][0]}〜¥{p['budget'][1]}"
        cuisine_txt = ", ".join(p["cuisine"]) if p["cuisine"] else "-"
        blocks += [
            {"type": "header", "text": {"type": "plain_text", "text": header}},
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"*予算*: {budget_txt}\n*ジャンル*: {cuisine_txt}\n{shops_md}"},
            },
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "この案に投票"},
                        "value": str(i),
                        "action_id": "vote_proposal",
                    }
                ],
            },
            {"type": "divider"},
        ]
    return blocks

def _tally_blocks(counter: Dict[int, int], eligible_total: int, voted_count: int) -> List[Dict]:
    """現在の集計状況を表示するためのBlock Kit。"""
    bar = lambda n: "█" * n
    lines = [
        f"*提案1*: {counter.get(1,0)} 票",
        f"*提案2*: {counter.get(2,0)} 票",
        f"*提案3*: {counter.get(3,0)} 票",
        f"_投票済み_: {voted_count}/{eligible_total}",
    ]
    return [
        {"type":"section","text":{"type":"mrkdwn","text":"\n".join(lines)}},
    ]

def register_kanji_flow(app: App) -> None:
    # 開始：参加可否
    @app.command("/幹事開始")
    def start(ack, body, say):
        ack()
        res = say(
            text="🍻 幹事開始！まずは *参加可否* を教えてください",
            blocks=[
                {"type": "section", "text": {"type": "mrkdwn", "text": "まずは *参加可否* を教えてください"}},
                {
                    "type": "actions",
                    "elements": [
                        {"type": "button", "text": {"type": "plain_text", "text": "参加"}, "value": "yes", "action_id": "attend_yes"},
                        {"type": "button", "text": {"type": "plain_text", "text": "未定"}, "value": "maybe", "action_id": "attend_maybe"},
                        {"type": "button", "text": {"type": "plain_text", "text": "不参加"}, "value": "no", "action_id": "attend_no"},
                    ],
                },
            ],
        )
        thread_ts = res["ts"]
        create_plan(thread_ts, body["channel_id"])

    # 参加可否（共通）
    @app.action({"action_id": "attend_yes"})
    @app.action({"action_id": "attend_maybe"})
    @app.action({"action_id": "attend_no"})
    def on_attendance(ack, body, action, client):
        ack()
        msg = body.get("message", {})
        thread_ts = msg.get("thread_ts") or msg.get("ts")
        user_id = body["user"]["id"]
        attendance = action["value"]
        upsert_participant(thread_ts, user_id, {"attendance": attendance})

        # 参加/未定のみ日付モーダルへ
        if attendance in ("yes", "maybe"):
            client.views_open(
                trigger_id=body["trigger_id"],
                view={
                    "type": "modal",
                    "callback_id": "pick_dates",
                    "private_metadata": json.dumps({"thread_ts": thread_ts}),
                    "title": {"type": "plain_text", "text": "候補日を選択"},
                    "submit": {"type": "plain_text", "text": "保存"},
                    "blocks": [
                        {"type": "input", "block_id": "d1", "label": {"type": "plain_text", "text": "第1候補"},
                         "element": {"type": "datepicker", "action_id": "date"}},
                        {"type": "input", "block_id": "d2", "label": {"type": "plain_text", "text": "第2候補（任意）"}, "optional": True,
                         "element": {"type": "datepicker", "action_id": "date"}},
                    ],
                },
            )

    # 日付モーダル保存 → 希望モーダルへ
    @app.view("pick_dates")
    def on_dates(ack, body, view, client):
        ack()
        meta = json.loads(view["private_metadata"])
        thread_ts = meta["thread_ts"]
        user_id = body["user"]["id"]

        def pick(block_id):
            state = view["state"]["values"].get(block_id, {})
            elem = state.get("date")
            return elem.get("selected_date") if elem else None

        d1 = pick("d1")
        d2 = pick("d2")
        dates = [d for d in [d1, d2] if d]
        if dates:
            upsert_participant(thread_ts, user_id, {"dates": dates})

        client.views_open(
            trigger_id=body["trigger_id"],
            view={
                "type": "modal",
                "callback_id": "prefs_input",
                "private_metadata": json.dumps({"thread_ts": thread_ts}),
                "title": {"type": "plain_text", "text": "希望を入力"},
                "submit": {"type": "plain_text", "text": "保存"},
                "blocks": [
                    {"type": "input", "block_id": "area", "optional": True,
                     "label": {"type": "plain_text", "text": "エリア（例：新宿/渋谷など）"},
                     "element": {"type": "plain_text_input", "action_id": "val"}},
                    {"type": "input", "block_id": "budget", "optional": True,
                     "label": {"type": "plain_text", "text": "予算（例：3000-5000）"},
                     "element": {"type": "plain_text_input", "action_id": "val"}},
                    {"type": "input", "block_id": "cuisine", "optional": True,
                     "label": {"type": "plain_text", "text": "ジャンル（例：焼き鳥, 居酒屋）"},
                     "element": {"type": "plain_text_input", "action_id": "val"}},
                ],
            },
        )

    @app.view("prefs_input")
    def on_prefs(ack, body, view):
        ack()
        meta = json.loads(view["private_metadata"])
        thread_ts = meta["thread_ts"]
        user_id = body["user"]["id"]

        vals = view["state"]["values"]
        area = vals.get("area", {}).get("val", {}).get("value")
        budget_raw = vals.get("budget", {}).get("val", {}).get("value")
        cuisine = vals.get("cuisine", {}).get("val", {}).get("value")

        budget_min = budget_max = None
        if budget_raw and "-" in budget_raw:
            try:
                bmin, bmax = budget_raw.split("-", 1)
                budget_min, budget_max = int(bmin), int(bmax)
            except Exception:
                pass

        fields = {}
        if area:
            fields["area"] = area.strip()
        if budget_min is not None and budget_max is not None:
            fields["budget_min"] = budget_min
            fields["budget_max"] = budget_max
        if cuisine:
            fields["cuisine"] = cuisine.strip()

        if fields:
            upsert_participant(thread_ts, user_id, fields)

    # 提案作成
    @app.command("/幹事提案")
    def proposals(ack, body, say, logger):
        ack()
        # 1) スレッド内で実行されたら、そのスレッドの ts を使う
        thread_ts = body.get("thread_ts")
        channel_id = body.get("channel_id")
        if not thread_ts and channel_id:
            # 2) スレッド外で実行されたら、同チャンネルの“最新の企画スレッド”を推定
            thread_ts = get_latest_plan_thread(channel_id)
        if not thread_ts:
            say(text="企画スレッドが見つかりません。`/幹事開始` を打ったスレッド内で `/幹事提案` を実行してください。")
            return
        # 以降は企画スレッドに返信する
        say(text="集計中…", thread_ts=thread_ts)

        rows = list_participants(thread_ts)
        if not rows:
            say(text="まだ回答がありません。/幹事開始 で募集を始めてください。", thread_ts=thread_ts)
            return

        agg = _participants_summary(rows)
        top_dates = _pick_top_dates(agg["date_counts"], k=3)
        if not top_dates:
            from datetime import date, timedelta
            today = date.today()
            top_dates = [str(today + timedelta(days=i * 7)) for i in range(3)]

        proposals = []
        for d in top_dates:
            shops = search_shops_api(
                area=agg["area"],
                budget_min=agg["budget"][0],
                budget_max=agg["budget"][1],
                cuisine=", ".join(agg["cuisine"]) if agg["cuisine"] else None,
                size=5,
            )
            proposals.append(
                {"date": d, "area": agg["area"], "budget": agg["budget"], "cuisine": agg["cuisine"], "shops": shops}
            )

        blocks = _proposal_blocks(proposals)
        say(text="3つの候補を提示します。投票してください！", blocks=blocks, thread_ts=thread_ts)

    # 投票
    @app.action("vote_proposal")
    def on_vote(ack, body, action, say, client):
        ack()
        idx = int(action["value"])
        user_id = body["user"]["id"]
        msg = body.get("message", {})
        thread_ts = msg.get("thread_ts") or msg.get("ts")
        record_vote(thread_ts, user_id, idx)
        client.chat_postEphemeral(
            channel=body["channel"]["id"],
            user=user_id,
            text=f"提案{idx}に投票しました！",
            thread_ts=thread_ts,
        )

        # --- 自動集計＆自動確定 ---
        eligible = eligible_voter_ids(thread_ts)
        counter = tally_votes(thread_ts)
        voted = voters_who_voted(thread_ts)

        # 1) 集計の進捗をスレッドに共有（控えめに一言）
        say(text=f"投票を更新: {len(voted)}/{len(eligible)}名が投票済みです。", thread_ts=thread_ts)

        # 2) 全員が投票済みなら自動確定
        if len(eligible) > 0 and set(voted) >= set(eligible):
            # 勝者を決定（最大票。タイのときは番号が小さい案を優先）
            winner, _ = max(counter.items(), key=lambda kv: (kv[1], -kv[0]))
            say(
                text=f":tada: *投票が出揃いました！最終案は 提案{winner} です。*",
                thread_ts=thread_ts,
            )

    # ---- 追加：現在の集計を出す ----
    @app.command("/幹事集計")
    def cmd_tally(ack, body, say):
        ack()
        thread_ts = body.get("thread_ts") or get_latest_plan_thread(body.get("channel_id"))
        if not thread_ts:
            say(text="集計対象の企画が見つかりません。/幹事開始 のスレッド内で実行してください。")
            return
        eligible = eligible_voter_ids(thread_ts)
        counter = tally_votes(thread_ts)
        voted = voters_who_voted(thread_ts)
        blocks = _tally_blocks(counter, eligible_total=len(eligible), voted_count=len(voted))
        say(text="現在の投票状況です。", blocks=blocks, thread_ts=thread_ts)

    # ---- 追加：手動で確定する ----
    @app.command("/幹事確定")
    def cmd_finalize(ack, body, say):
        ack()
        thread_ts = body.get("thread_ts") or get_latest_plan_thread(body.get("channel_id"))
        if not thread_ts:
            say(text="確定対象の企画が見つかりません。/幹事開始 のスレッド内で実行してください。")
            return
        counter = tally_votes(thread_ts)
        winner, _ = max(counter.items(), key=lambda kv: (kv[1], -kv[0]))
        say(text=f":white_check_mark: 幹事によって *提案{winner}* を最終案として確定しました。", thread_ts=thread_ts)