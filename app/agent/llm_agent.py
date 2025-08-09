
"""幹事郎プロジェクトで使用されるLLMベースのエージェント。"""

from __future__ import annotations

import os
from typing import Optional


import google.generativeai as genai

from .base_agent import BaseAgent


class LLMAgent(BaseAgent):

    """Geminiのチャットモデルで応答を生成するエージェント。"""

    def __init__(
        self,
        name: str = "LLMAgent",
        system_prompt: Optional[str] = None,
        model: Optional[str] = None,
    ) -> None:
        super().__init__(name)

        # Geminiクライアントを設定。APIキーが指定されない場合は環境変数などから取得する。
        api_key = os.environ.get("GEMINI_API_KEY")
        if api_key:
            genai.configure(api_key=api_key)


        # エージェントの振る舞いを定義するシステムプロンプト。
        # 各サブクラスは役割に応じて独自のプロンプトを渡せる。
        self.system_prompt = (
            system_prompt or "あなたは日本語で応答する有能なアシスタントです。"
        )

        # 使用するモデルは環境変数で上書きでき、デフォルトは gemini-1.5-flash
        self.model_name = model or os.environ.get("GEMINI_MODEL", "gemini-1.5-flash")
        self.model = genai.GenerativeModel(
            model_name=self.model_name,
            system_instruction=self.system_prompt,
        )

    def respond(self, message: str) -> str:
        # 会話をGeminiモデルに送信し、最初の応答テキストを返す。
        response = self.model.generate_content(message)
        return response.text.strip()

