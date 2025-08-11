"""LLM Agents using Google Gemini for summarization and conversation."""

from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, Optional, Tuple

import google.generativeai as genai

DEFAULT_SYSTEM_PROMPT = "あなたは日本語で応答する有能なアシスタントです。"
EMPTY_JSON = {"decisions": [], "open_issues": [], "context": [], "links": []}

SummaryPayload = Dict[str, Any]


class SummarizerAgent:
    """Agent responsible for producing conversation summaries."""

    def __init__(self, model: Optional[str] = None) -> None:
        api_key = os.environ.get("GEMINI_API_KEY_SUM")
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY_SUM is not set")
        genai.configure(api_key=api_key)
        self.model_name = model or os.environ.get("GEMINI_MODEL_SUM", "gemini-1.5-flash")
        self.model = genai.GenerativeModel(model_name=self.model_name)

    def summarize(
        self,
        prev_summary: Optional[SummaryPayload],
        user_text: str,
        assistant_last: Optional[str] = None,
    ) -> Tuple[str, Dict[str, Any]]:
        """Return updated summary text and JSON structure."""
        prev_text = prev_summary.get("text") if prev_summary else ""
        prev_json = prev_summary.get("json") if prev_summary else EMPTY_JSON
        prompt = (
            "前回までの要約:\n" + (prev_text or "なし") +
            "\n今回ユーザー: " + user_text +
            ("\n直前アシスタント: " + assistant_last if assistant_last else "") +
            "\n上記を踏まえて、更新された要約を以下の形式で出力してください。"
            "\n1行のテキスト要約\nJSON:" + json.dumps(EMPTY_JSON, ensure_ascii=False)
        )
        try:
            res = self.model.generate_content(prompt)
            raw = (res.text or "").strip()
        except Exception:
            raw = ""
        js = self._extract_json(raw)
        text_only = raw
        if js:
            json_str = json.dumps(js, ensure_ascii=False)
            text_only = raw.replace(json_str, "").strip()
        merged = self._merge_json(prev_json, js)
        return (text_only or prev_text or ""), merged

    @staticmethod
    def _extract_json(text: str) -> Dict[str, Any]:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group(0))
                if isinstance(data, dict):
                    return data
            except json.JSONDecodeError:
                pass
        return {}

    def _merge_json(
        self, prev: Dict[str, Any], new: Dict[str, Any]
    ) -> Dict[str, Any]:
        result: Dict[str, Any] = {k: list(prev.get(k, [])) for k in EMPTY_JSON}
        for key in EMPTY_JSON:
            items = result[key]
            items.extend(new.get(key, []))
            seen = set()
            deduped = []
            for item in items:
                if item not in seen:
                    seen.add(item)
                    deduped.append(item)
            result[key] = deduped
        return result


class ConversationalAgent:
    """Agent generating replies using the latest summary."""

    def __init__(
        self,
        name: str = "ConversationalAgent",
        system_prompt: Optional[str] = None,
        model: Optional[str] = None,
    ) -> None:
        self.name = name
        api_key = os.environ.get("GEMINI_API_KEY_CONV")
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY_CONV is not set")
        genai.configure(api_key=api_key)
        self.system_prompt = system_prompt or DEFAULT_SYSTEM_PROMPT
        self.model_name = model or os.environ.get("GEMINI_MODEL_CONV", "gemini-1.5-flash")
        self.model = genai.GenerativeModel(
            model_name=self.model_name,
            system_instruction=self.system_prompt,
        )

    def reply(self, summary: SummaryPayload, user_text: str) -> str:
        if not user_text or not user_text.strip():
            return "ご用件を一言で教えてください。"
        version = summary.get("version")
        summary_text = summary.get("text", "")
        prompt = (
            (f"これまでの要約(ver.{version}):\n{summary_text}\n" if summary_text else "")
            + f"ユーザー: {user_text}"
        )
        try:
            res = self.model.generate_content(prompt)
            text = (res.text or "").strip()
            if not text:
                return "すみません、うまく答えを生成できませんでした。もう少し具体的に教えてください。"
            return text
        except Exception as e:
            return f"エラーが発生しました。少し時間をおいて再試行してください。（詳細: {type(e).__name__})"


# Backward compatibility
LLMAgent = ConversationalAgent
