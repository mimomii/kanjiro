"""SQLite Data Access Object for conversation summaries."""

from __future__ import annotations

import json
import hashlib
import os
import sqlite3
from typing import Any, Dict, Optional

SummaryDict = Dict[str, Any]

EMPTY_SUMMARY = {
    "decisions": [],
    "open_issues": [],
    "context": [],
    "links": [],
}


def init_db(db_path: str) -> None:
    """Initialize database and ensure table exists."""
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS summaries (
            conv_id TEXT,
            version INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            author_agent TEXT,
            summary_text TEXT,
            summary_json TEXT,
            input_hash TEXT,
            PRIMARY KEY (conv_id, version)
        )
        """
    )
    cur.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_summaries_conv_id_version
            ON summaries(conv_id, version DESC)
        """
    )
    conn.commit()
    conn.close()


def get_latest_summary(db_path: str, conv_id: str) -> Optional[SummaryDict]:
    """Retrieve latest summary for a conversation."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(
        "SELECT version, summary_text, summary_json, input_hash FROM summaries"
        " WHERE conv_id=? ORDER BY version DESC LIMIT 1",
        (conv_id,),
    )
    row = cur.fetchone()
    conn.close()
    if not row:
        return None
    try:
        js = json.loads(row["summary_json"]) if row["summary_json"] else {}
    except json.JSONDecodeError:
        js = {}
    return {
        "version": row["version"],
        "text": row["summary_text"],
        "json": js,
        "input_hash": row["input_hash"],
    }


def save_new_summary(
    db_path: str,
    conv_id: str,
    author: str,
    text: str,
    js_dict: SummaryDict,
    input_hash: str,
) -> int:
    """Save new summary if not already stored. Returns version."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(
        "SELECT version FROM summaries WHERE conv_id=? AND input_hash=? LIMIT 1",
        (conv_id, input_hash),
    )
    row = cur.fetchone()
    if row:
        conn.close()
        return int(row["version"])
    cur.execute(
        "SELECT COALESCE(MAX(version),0) as v FROM summaries WHERE conv_id=?",
        (conv_id,),
    )
    last_version = int(cur.fetchone()["v"])
    new_version = last_version + 1
    cur.execute(
        "INSERT INTO summaries (conv_id, version, author_agent, summary_text, summary_json, input_hash)"
        " VALUES (?,?,?,?,?,?)",
        (
            conv_id,
            new_version,
            author,
            text,
            json.dumps(js_dict, ensure_ascii=False),
            input_hash,
        ),
    )
    conn.commit()
    conn.close()
    return new_version


def make_input_hash(
    prev_summary: Optional[SummaryDict],
    turn_user: str,
    turn_assistant: Optional[str] = None,
) -> str:
    """Compute SHA256 hash of conversation state for idempotency."""
    prev_text = ""
    prev_json = ""
    if prev_summary:
        prev_text = prev_summary.get("text", "")
        prev_json = json.dumps(prev_summary.get("json", {}), sort_keys=True)
    payload = "||".join([prev_text, prev_json, turn_user or "", turn_assistant or ""])
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
