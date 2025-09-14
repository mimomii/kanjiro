# app/flows/kanji_flow.py
from __future__ import annotations
import json
from typing import Dict, List, Optional
from slack_bolt import App
from app.agent.llm_agent import LLMAgent

from app.store import (
    create_plan, upsert_participant, list_participants, record_vote,
    get_latest_plan_thread, eligible_voter_ids, tally_votes, voters_who_voted,
    get_channel_id,
)
from app.services.shops import search_shops_api


# ===== 集計系ユーティリティ =====

def _participants_summary(rows) -> Dict:
    import statistics
    from collections import Counter

    yes_users = [r for r in rows if (r.get("attendance") in ("yes", "maybe"))]

    # dates: 出現回数
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

    # cuisine: 上位3（カンマ区切り集計）
    from collections import Counter as C
    cuisines_raw = [r.get("cuisine") for r in yes_users if r.get("cuisine")]
    cuisine_list: List[str] = []
    for c in cuisines_raw:
        cuisine_list.extend([x.strip() for x in c.split(",") if x.strip()])
    top_cuisine = [c for c, _ in C(cuisine_list).most_common(3)] if cuisine_list else []

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
    lines = [
        f"*提案1*: {counter.get(1,0)} 票",
        f"*提案2*: {counter.get(2,0)} 票",
        f"*提案3*: {counter.get(3,0)} 票",
        f"_投票済み_: {voted_count}/{eligible_total}",
    ]
    return [{"type": "section", "text": {"type": "mrkdwn", "text": "\n".join(lines)}}]


def _alignment_prompt(agg: Dict, rows: List[Dict], summary: str) -> str:
    """“すり合わせ”誘導文を LLM に作らせるためのプロンプト。"""
    needers = [r for r in rows if r.get("attendance") in ("yes","maybe")]
    sample = {
        "top_dates_hint": list(agg["date_counts"].keys()),
        "area_mode": agg["area"],
        "budget": agg["budget"],
        "cuisine_top": agg["cuisine"],
        "participants_count": len(needers),
    }
    return (
        "次の情報を踏まえて、Slackチャンネル向けの“すり合わせ”誘導メッセージを日本語で作成してください。\n"
        "- 目的: メンバー間で日程・エリア・ジャンルの希望をすり合わせる\n"
        "- 形式: 箇条書き3〜5行 + 短い締めの一言。@here は付けない\n"
        f"- 集計サマリの要点: {sample}\n"
        f"- 最近の会話要約: {summary[:400]}\n"
        "注意: 強制はせず、相違点がある場合は第2候補日・隣接エリア・類似ジャンルなど“落とし所”をやさしく提案してください。"
    )


# ===== メイン登録 =====

def register_kanji_flow(app: App, llm: LLMAgent) -> None:
    # /幹事説明：定型の利用ガイド
    @app.command("/幹事説明")
    def cmd_help(ack, body, say):
        ack()
        guide = (
            "*幹事郎の使い方*\n"
            "1) `/幹事開始`：参加可否ボタンが出ます。参加/未定の人は候補日を入力します。\n"
            "2) 日付の次に、希望（エリア/予算/ジャンル）をモーダルで入力します。\n"
            "3) 進捗は `/幹事すり合わせ` で確認できます（サマリー＆“すり合わせ”案内をチャンネルに投稿）。\n"
            "4) `/幹事提案`：集計結果と会話要約をもとに3つの案（各案に店候補リンク）を提示します。\n"
            "5) 各案に“投票”ボタンで投票します。`/幹事集計`で途中経過を確認できます。\n"
            "6) 全員が投票すると、自動で最終案をチャンネルに宣言します（または`/幹事確定`で手動確定）。\n"
            "7) 店のリンクは安全なサイトに限定されます（食べログ/ホットペッパー/ぐるなび/一休/Retty）。\n"
        )
        say(text=guide)

    # /回答状況：回答サマリー + “すり合わせ”案内を投稿
    @app.command("/幹事すり合わせ")
    def cmd_status(ack, body, say, client, logger):
        ack()
        thread_ts = body.get("thread_ts") or get_latest_plan_thread(body.get("channel_id"))
        ch = body.get("channel_id")
        if not thread_ts or not ch:
            say(text="企画スレッドが見つかりません。/幹事開始 のスレッド内で実行するか、同チャンネルで一度 /幹事開始 を打ってください。")
            return

        try:
            rows = list_participants(thread_ts)
            if not rows:
                say(text="まだ回答がありません。/幹事開始 で募集を始めてください。")
                return

            # 集計
            agg = _participants_summary(rows)
            date_lines = [f"- {d}: {c}名" for d, c in agg["date_counts"].most_common(5)]
            area = agg["area"] or "-"
            budget = f"¥{agg['budget'][0]}〜¥{agg['budget'][1]}"
            cuisine = ", ".join(agg["cuisine"]) if agg["cuisine"] else "-"

            total = len(rows)
            yes_cnt  = sum(1 for r in rows if r.get("attendance") == "yes")
            maybe_cnt = sum(1 for r in rows if r.get("attendance") == "maybe")
            no_cnt   = sum(1 for r in rows if r.get("attendance") == "no")
            filled_cnt = sum(
                1 for r in rows
                if (r.get("attendance") in ("yes","maybe") and (r.get("dates") or []))
                   or (r.get("attendance") == "no")
            )

            # すり合わせ案内（LLM）
            try:
                convo_summary = llm.get_summary()
                prompt = _alignment_prompt(agg, rows, convo_summary)
                align_msg = llm.respond(prompt)
            except Exception:
                align_msg = "入力が出そろってきました。第2候補日や近隣エリア、近いジャンルを出し合ってすり合わせましょう！"

            # 投稿（チャンネルに直接）
            blocks = [
                {"type": "header", "text": {"type": "plain_text", "text": "回答状況まとめ"}},
                {"type": "section", "text": {"type": "mrkdwn",
                    "text": (
                        f"*回答数*: {filled_cnt}/{total}\n"
                        f"*参加*: {yes_cnt}  *未定*: {maybe_cnt}  *不参加*: {no_cnt}\n"
                        f"*エリア傾向*: {area}\n"
                        f"*予算中央値*: {budget}\n"
                        f"*ジャンルトップ*: {cuisine}\n"
                    )
                }},
                {"type": "section", "text": {"type": "mrkdwn",
                    "text": "*候補日（上位）:*\n" + ("\n".join(date_lines) if date_lines else "-")}
                },
                {"type": "divider"},
                {"type": "section", "text": {"type": "mrkdwn",
                    "text": f":speech_balloon: *すり合わせの案内*\n{align_msg}"}}
            ]
            client.chat_postMessage(channel=ch, text="回答状況まとめ", blocks=blocks)

        except Exception as e:
            logger.exception(e)
            say(text="回答状況の集計でエラーが発生しました。もう一度お試しください。")

    # 開始：参加可否
    @app.command("/幹事開始")
    def start(ack, body, client, logger):
        ack()
        channel_id = body["channel_id"]
        try:
            res = client.chat_postMessage(
                channel=channel_id,
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
            create_plan(thread_ts, channel_id)
        except Exception as e:
            logger.exception(e)

    # 参加可否（共通）
    @app.action({"action_id": "attend_yes"})
    @app.action({"action_id": "attend_maybe"})
    @app.action({"action_id": "attend_no"})
    def on_attendance(ack, body, action, client, logger):
        ack()
        try:
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
                        "submit": {"type": "plain_text", "text": "次へ"},
                        "close": {"type": "plain_text", "text": "キャンセル"},
                        "blocks": [
                            {"type": "input", "block_id": "d1", "label": {"type": "plain_text", "text": "第1候補"},
                             "element": {"type": "datepicker", "action_id": "date"}},
                            {"type": "input", "block_id": "d2", "label": {"type": "plain_text", "text": "第2候補（任意）"}, "optional": True,
                             "element": {"type": "datepicker", "action_id": "date"}},
                            {"type": "input", "block_id": "d3", "label": {"type": "plain_text", "text": "第3候補（任意）"}, "optional": True,
                             "element": {"type": "datepicker", "action_id": "date"}},
                        ],
                    },
                )
        except Exception as e:
            logger.exception(e)

    # 日付モーダルの submit → 希望入力モーダルへ update 遷移
    @app.view("pick_dates")
    def on_pick_dates(ack, body, view, client, logger):
        try:
            meta = json.loads(view.get("private_metadata") or "{}")
            thread_ts = meta.get("thread_ts")
            user_id = body["user"]["id"]

            sel: List[str] = []
            for bid in ["d1", "d2", "d3"]:
                block = view["state"]["values"].get(bid, {})
                selected = next((v.get("selected_date") for v in block.values() if isinstance(v, dict)), None)
                if selected:
                    sel.append(selected)

            upsert_participant(thread_ts, user_id, {"dates": sel})

            ack(response_action="update", view={
                "type": "modal",
                "callback_id": "prefs_input",
                "private_metadata": json.dumps({"thread_ts": thread_ts}),
                "title": {"type": "plain_text", "text": "希望を入力"},
                "submit": {"type": "plain_text", "text": "保存"},
                "close": {"type": "plain_text", "text": "戻る"},
                "blocks": [
                    {"type": "input", "block_id": "area", "optional": True,
                     "label": {"type": "plain_text", "text": "希望エリア（例: 渋谷・新宿など）"},
                     "element": {"type": "plain_text_input", "action_id": "v"}},
                    {"type": "input", "block_id": "budget_min", "optional": True,
                     "label": {"type": "plain_text", "text": "予算 下限（数値・円）"},
                     "element": {"type": "plain_text_input", "action_id": "v", "placeholder": {"type":"plain_text","text":"3000"}, "dispatch_action_config":{"trigger_actions_on":["on_enter_pressed"]}}},
                    {"type": "input", "block_id": "budget_max", "optional": True,
                     "label": {"type": "plain_text", "text": "予算 上限（数値・円）"},
                     "element": {"type": "plain_text_input", "action_id": "v", "placeholder": {"type":"plain_text","text":"5000"}}},
                    {"type": "input", "block_id": "cuisine", "optional": True,
                     "label": {"type": "plain_text", "text": "希望ジャンル（カンマ区切り）"},
                     "element": {"type": "plain_text_input", "action_id": "v", "placeholder": {"type":"plain_text","text":"居酒屋, 焼き鳥, 魚介"}}},
                ],
            })
        except Exception as e:
            try:
                ack()
            except Exception:
                pass
            logger.exception(e)

    # 希望入力モーダルの submit
    @app.view("prefs_input")
    def on_prefs(ack, body, view, client, logger):
        try:
            ack()
            meta = json.loads(view.get("private_metadata") or "{}")
            thread_ts = meta.get("thread_ts")
            user_id = body["user"]["id"]

            def _get_val(block_id: str) -> Optional[str]:
                block = view["state"]["values"].get(block_id, {})
                return next((v.get("value") for v in block.values() if isinstance(v, dict)), None)

            area = (_get_val("area") or "").strip() or None
            cuisine = (_get_val("cuisine") or "").strip() or None

            bmin_raw = (_get_val("budget_min") or "").strip()
            bmax_raw = (_get_val("budget_max") or "").strip()
            def _to_int(s: str) -> Optional[int]:
                try:
                    return int(s.replace(",", "").replace("円","").strip())
                except Exception:
                    return None
            budget_min = _to_int(bmin_raw) if bmin_raw else None
            budget_max = _to_int(bmax_raw) if bmax_raw else None

            upsert_participant(thread_ts, user_id, {
                "area": area,
                "budget_min": budget_min,
                "budget_max": budget_max,
                "cuisine": cuisine,
            })

            # 自動投稿は完全廃止（ここでは何もしない）

            # 本人に控えめに通知（チャンネルにエフェメラル）
            ch = get_channel_id(thread_ts)
            if ch:
                client.chat_postEphemeral(
                    channel=ch,
                    user=user_id,
                    text="希望を保存しました。ありがとうございます！",
                )

        except Exception as e:
            logger.exception(e)

    # 提案作成
    @app.command("/幹事提案")
    def proposals(ack, body, say, logger, client):
        ack()
        thread_ts = body.get("thread_ts")
        channel_id = body.get("channel_id")
        if not thread_ts and channel_id:
            thread_ts = get_latest_plan_thread(channel_id)
        if not thread_ts:
            say(text="企画スレッドが見つかりません。`/幹事開始` を打ったスレッド内で `/幹事提案` を実行してください。")
            return
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
        convo_summary = llm.get_summary()
        for d in top_dates:
            shops = search_shops_api(
                area=agg["area"],
                budget_min=agg["budget"][0],
                budget_max=agg["budget"][1],
                cuisine=", ".join(agg["cuisine"]) if agg["cuisine"] else None,
                size=5,
                extra_keywords=convo_summary,
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

        ch = get_channel_id(thread_ts)
        if ch:
            client.chat_postEphemeral(
                channel=ch,
                user=user_id,
                text=f"提案{idx}に投票しました！",
            )

        # --- 自動集計＆自動確定 ---
        eligible = eligible_voter_ids(thread_ts)
        counter = tally_votes(thread_ts)
        voted = voters_who_voted(thread_ts)

        # 1) 集計の進捗をスレッドに共有（従来通り）
        say(text=f"投票を更新: {len(voted)}/{len(eligible)}名が投票済みです。", thread_ts=thread_ts)

        # 2) 全員が投票済みなら自動確定 → チャンネルに直接告知
        if len(eligible) > 0 and set(voted) >= set(eligible):
            winner, _ = max(counter.items(), key=lambda kv: (kv[1], -kv[0]))
            if ch:
                client.chat_postMessage(
                    channel=ch,
                    text=f":tada: *投票が出揃いました！最終案は 提案{winner} です。*",
                )

    # ---- 現在の集計を出す ----
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

    # ---- 手動で確定する ----
    @app.command("/幹事確定")
    def cmd_finalize(ack, body, say):
        ack()
        thread_ts = body.get("thread_ts") or get_latest_plan_thread(body.get("channel_id"))
        if not thread_ts:
            say(text="確定対象の企画が見つかりません。/幹事開始 のスレッド内で実行してください。")
            return
        counter = tally_votes(thread_ts)
        if not counter:
            say(text="投票がありません。/幹事提案 で候補提示＆投票を開始してください。", thread_ts=thread_ts)
            return
        winner, _ = max(counter.items(), key=lambda kv: (kv[1], -kv[0]))
        ch = get_channel_id(thread_ts)
        if ch:
            # 手動確定もチャンネルに直接
            say(text=f":white_check_mark: 幹事によって *提案{winner}* を最終案として確定しました。", channel=ch)
        else:
            say(text=f":white_check_mark: 幹事によって *提案{winner}* を最終案として確定しました。", thread_ts=thread_ts)
