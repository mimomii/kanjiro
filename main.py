import argparse
import json
import logging
import os
import sqlite3
import sys
from typing import Dict, List, Optional, Tuple
from dotenv import load_dotenv

FALLBACK_TEXT = "すみません、うまく生成できませんでした。"
DB_PATH = "memory.db"

logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')
load_dotenv()


def get_conn(path: str = DB_PATH) -> Optional[sqlite3.Connection]:
    try:
        conn = sqlite3.connect(path, timeout=30)
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS messages (
                conv_id TEXT,
                role TEXT,
                text TEXT,
                ts DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS summaries (
                conv_id TEXT PRIMARY KEY,
                version INTEGER,
                text TEXT
            )
            """
        )
        return conn
    except Exception:
        logging.error("db_connect_failed", exc_info=True)
        return None


def save_message(conn: Optional[sqlite3.Connection], conv_id: str, role: str, text: str) -> None:
    if not conn:
        return
    try:
        with conn:
            conn.execute(
                "INSERT INTO messages (conv_id, role, text) VALUES (?, ?, ?)",
                (conv_id, role, text),
            )
        logging.info("saved_message role=%s conv_id=%s", role, conv_id)
    except Exception:
        logging.error("db_save_failed role=%s conv_id=%s", role, conv_id, exc_info=True)


def fetch_messages(conn: Optional[sqlite3.Connection], conv_id: str, limit: int = 20) -> List[Tuple[str, str]]:
    if not conn:
        return []
    try:
        cur = conn.execute(
            "SELECT role, text FROM messages WHERE conv_id=? ORDER BY ts DESC LIMIT ?",
            (conv_id, limit),
        )
        rows = cur.fetchall()
        rows.reverse()
        return rows
    except Exception:
        logging.error("db_read_failed conv_id=%s", conv_id, exc_info=True)
        return []


def get_summary(conn: Optional[sqlite3.Connection], conv_id: str) -> Dict[str, object]:
    if not conn:
        return {"version": 0, "text": ""}
    try:
        cur = conn.execute(
            "SELECT version, text FROM summaries WHERE conv_id=?", (conv_id,)
        )
        row = cur.fetchone()
        if row:
            return {"version": row[0], "text": row[1]}
    except Exception:
        logging.error("db_summary_fetch_failed conv_id=%s", conv_id, exc_info=True)
    return {"version": 0, "text": ""}


def build_prompt(conv_id: str, summary: Dict[str, object], messages: List[Tuple[str, str]]) -> str:
    parts: List[str] = []
    if summary.get("text"):
        parts.append(f"要約:\n{summary['text']}")
    for role, text in messages:
        parts.append(f"{role}:{text}")
    prompt = "\n".join(parts) + "\nassistant:"
    tokens = len(prompt.split())
    logging.info("built_prompt conv_id=%s tokens=%d", conv_id, tokens)
    return prompt


class LLM:
    def __init__(self) -> None:
        self.provider = os.environ.get("LLM_PROVIDER", "gemini").lower()
        if self.provider == "openai":
            api_key = os.environ.get("OPENAI_API_KEY")
            if not api_key:
                logging.error("OPENAI_API_KEY is not set")
                sys.exit(1)
            try:
                from openai import OpenAI  # type: ignore

                self.client = OpenAI(api_key=api_key)
            except Exception:
                logging.error("openai_init_failed", exc_info=True)
                sys.exit(1)
        else:  # gemini by default
            api_key = os.environ.get("GEMINI_API_KEY")
            if not api_key:
                logging.error("GEMINI_API_KEY is not set")
                sys.exit(1)
            try:
                import google.generativeai as genai  # type: ignore

                genai.configure(api_key=api_key)
                model_name = os.environ.get("GEMINI_MODEL", "gemini-1.5-flash")
                self.client = genai.GenerativeModel(model_name)
                self.provider = "gemini"
            except Exception:
                logging.error("gemini_init_failed", exc_info=True)
                sys.exit(1)

    def generate(self, prompt: str) -> str:
        logging.info("llm_called provider=%s", self.provider)
        try:
            if self.provider == "openai":
                res = self.client.chat.completions.create(
                    model=os.environ.get("OPENAI_MODEL", "gpt-3.5-turbo"),
                    messages=[{"role": "user", "content": prompt}],
                    timeout=30,
                )
                text = (res.choices[0].message.content or "").strip()
            else:
                res = self.client.generate_content(
                    prompt, request_options={"timeout": 30}
                )
                text = (getattr(res, "text", "") or "").strip()
            if not text:
                raise ValueError("empty response")
            return text
        except Exception:
            logging.error("llm_failed provider=%s", self.provider, exc_info=True)
            return FALLBACK_TEXT


def maybe_update_summary(
    conn: Optional[sqlite3.Connection], conv_id: str, llm: LLM
) -> Dict[str, object]:
    summary = get_summary(conn, conv_id)
    try:
        messages = fetch_messages(conn, conv_id, limit=50)
        content = "\n".join([f"{r}:{t}" for r, t in messages])
        prompt = f"次の会話を短く要約してください:\n{content}"
        new_text = llm.generate(prompt)
        if not conn:
            return summary
        version = int(summary.get("version", 0)) + 1
        with conn:
            conn.execute(
                "REPLACE INTO summaries (conv_id, version, text) VALUES (?, ?, ?)",
                (conv_id, version, new_text),
            )
        logging.info("summary_updated conv_id=%s version=%d", conv_id, version)
        return {"version": version, "text": new_text}
    except Exception:
        logging.error("summary_update_failed conv_id=%s", conv_id, exc_info=True)
        return summary


def extract_json(text: str) -> Dict:
    if not text:
        return {}
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        try:
            start = text.find("{")
            end = text.rfind("}")
            if start != -1 and end != -1:
                return json.loads(text[start : end + 1])
        except Exception:
            pass
        logging.error("json_extract_failed", exc_info=True)
        return {}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--conv")
    parser.add_argument("--user")
    args = parser.parse_args()
    if not args.conv or not args.user:
        parser.print_usage()
        return 2

    conv_id = args.conv
    user_text = args.user
    logging.info("received_user conv_id=%s", conv_id)

    conn = get_conn()
    save_message(conn, conv_id, "user", user_text)
    summary = get_summary(conn, conv_id)
    messages = fetch_messages(conn, conv_id)
    prompt = build_prompt(conv_id, summary, messages)

    llm = LLM()
    reply = llm.generate(prompt)
    save_message(conn, conv_id, "assistant", reply)
    maybe_update_summary(conn, conv_id, llm)

    if conn:
        conn.close()
    print(reply)
    return 0


if __name__ == "__main__":
    sys.exit(main())
