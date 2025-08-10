"""Gemini を叩いてテキストを返す最小クラス。日本語デフォルト。"""

from __future__ import annotations
import os
from typing import Optional

import google.generativeai as genai


class LLMAgent:
    def __init__(
        self,
        name: str = "LLMAgent",
        system_prompt: Optional[str] = None,
        model: Optional[str] = None,
    ) -> None:
        self.name = name

        api_key = os.environ.get("GEMINI_API_KEY")
        # main.py 側で既に検証しているが、念のため
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY is not set")
        genai.configure(api_key=api_key)

        self.system_prompt = system_prompt or "あなたは日本語で応答する有能なアシスタントです。"
        self.model_name = model or os.environ.get("GEMINI_MODEL", "gemini-1.5-flash")

        # system_instruction は 1.5 系モデルで有効
        self.model = genai.GenerativeModel(
            model_name=self.model_name,
            system_instruction=self.system_prompt,
        )

    def respond(self, message: str) -> str:
        if not message or not message.strip():
            return "ご用件を一言で教えてください。"

        try:
            res = self.model.generate_content(message.strip())
            text = (res.text or "").strip()
            if not text:
                return "すみません、うまく答えを生成できませんでした。もう少し具体的に教えてください。"
            return text
        except Exception as e:
            # Slack で黙らないためのフォールバック
            return f"エラーが発生しました。少し時間をおいて再試行してください。（詳細: {type(e).__name__})"

