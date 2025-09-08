# app/store.py
from __future__ import annotations
from typing import Dict, List, Optional, Any

# 1スレッド＝1企画
# plans[thread_ts] = {"channel_id": "...", "title": Optional[str], "status": "attendance" | "dates" | "prefs" | "confirm" | "done"}
plans: Dict[str, Dict[str, Any]] = {}

# participants[(thread_ts, user_id)] = {
#   "attendance": "yes"|"no"|"maybe",
#   "dates": List[str],
#   "area": str,
#   "budget_min": int,
#   "budget_max": int,
#   "cuisine": str,  # comma-separated
# }
participants: Dict[tuple, Dict[str, Any]] = {}

# votes[(thread_ts, user_id)] = proposal_index (1..3)
votes: Dict[tuple, int] = {}


def create_plan(thread_ts: str, channel_id: str, title: Optional[str] = None) -> None:
    if thread_ts not in plans:
        plans[thread_ts] = {
            "channel_id": channel_id,
            "title": title,
            "status": "attendance",
        }


def update_plan_status(thread_ts: str, status: str) -> None:
    if thread_ts in plans:
        plans[thread_ts]["status"] = status


def upsert_participant(thread_ts: str, user_id: str, fields: Dict[str, Any]) -> None:
    key = (thread_ts, user_id)
    row = participants.get(key, {"dates": []})
    row.update(fields or {})
    # dates を文字列→配列統一
    if isinstance(row.get("dates"), str):
        # カンマ区切り等が来た場合の緩い吸収
        row["dates"] = [d.strip() for d in row["dates"].split(",") if d.strip()]
    participants[key] = row


def list_participants(thread_ts: str) -> List[Dict[str, Any]]:
    return [v for (t, _), v in participants.items() if t == thread_ts]


def record_vote(thread_ts: str, user_id: str, idx: int) -> None:
    votes[(thread_ts, user_id)] = idx

def get_latest_plan_thread(channel_id: str) -> Optional[str]:
    """
    同一チャンネルで最後に create_plan された thread_ts を返す。
    （インメモリなので “後勝ち” で最新扱い）
    """
    latest = None
    for ts, p in plans.items():
        if p.get("channel_id") == channel_id:
            latest = ts
    return latest

def eligible_voter_ids(thread_ts: str) -> List[str]:
    """投票対象（参加/未定）のユーザーID一覧。"""
    ids = []
    for (ts, uid), row in participants.items():
        if ts != thread_ts:
            continue
        if row.get("attendance") in ("yes", "maybe"):
            ids.append(uid)
    return ids

def tally_votes(thread_ts: str) -> Dict[int, int]:
    """proposal_index -> 票数 の辞書（1..3 をキーに集計）。"""
    counter: Dict[int, int] = {1: 0, 2: 0, 3: 0}
    for (ts, _uid), idx in votes.items():
        if ts != thread_ts:
            continue
        if idx in counter:
            counter[idx] += 1
    return counter

def voters_who_voted(thread_ts: str) -> List[str]:
    """すでに投票済みのユーザーID一覧。"""
    done = []
    for (ts, uid), _idx in votes.items():
        if ts == thread_ts:
            done.append(uid)
    return done    

def get_channel_id(thread_ts: str) -> Optional[str]:
    """企画スレッドのチャネルIDを返す。"""
    p = plans.get(thread_ts)
    return p.get("channel_id") if p else None