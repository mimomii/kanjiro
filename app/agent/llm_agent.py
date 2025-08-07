"""幹事郎プロジェクトで使用されるLLMベースのエージェント。"""

from __future__ import annotations

import os
from typing import Optional

from openai import OpenAI

from .base_agent import BaseAgent


class LLMAgent(BaseAgent):
    """OpenAIのチャットモデルで応答を生成するエージェント。"""

    def __init__(
        self,
        name: str = "LLMAgent",
        system_prompt: Optional[str] = None,
        model: Optional[str] = None,
    ) -> None:
        super().__init__(name)
        # OpenAIクライアントを設定。APIキーが指定されない場合は環境変数などから取得する。
        api_key = os.environ.get("OPENAI_API_KEY")
        self.client = OpenAI(api_key=api_key) if api_key else OpenAI()

        # エージェントの振る舞いを定義するシステムプロンプト。
        # 各サブクラスは役割に応じて独自のプロンプトを渡せる。
        self.system_prompt = (
            system_prompt or "あなたは日本語で応答する有能なアシスタントです。"
        )

        # 使用するモデルは環境変数で上書きでき、デフォルトはgpt-3.5-turbo
        self.model = model or os.environ.get("OPENAI_MODEL", "gpt-3.5-turbo")

    def respond(self, message: str) -> str:
        # 会話をOpenAIのChat Completions APIに送信し、最初の応答を返す。
        completion = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": message},
            ],
        )
        return completion.choices[0].message["content"].strip()

