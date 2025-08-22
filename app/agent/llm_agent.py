"""Gemini ベースの会話エージェント。

Slack での会話ごとにメモリを保持するため、`ConversationBufferMemory` と
ローリング要約を組み合わせた `ConversationSummaryBufferMemory` を用いて
コンテキストを管理する。応答生成と要約には別々の Gemini API キーを
使用する。
"""

from __future__ import annotations

import os
from typing import Dict, Optional

from langchain.chains import ConversationChain
from langchain.memory import ConversationSummaryBufferMemory
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_google_genai import ChatGoogleGenerativeAI


class LLMAgent:
    """Gemini を用いた会話エージェント。"""

    def __init__(
        self,
        name: str = "LLMAgent",
        system_prompt: Optional[str] = None,
        model: Optional[str] = None,
        max_token_limit: int = 1000,
    ) -> None:
        self.name = name
        self.system_prompt = (
            system_prompt or "あなたは飲み会の幹事AIです。参加者の希望を整理し、日時/場所/店を丁寧に提案します。"
        )

        main_key = os.environ.get("GEMINI_API_KEY_MAIN")
        summary_key = os.environ.get("GEMINI_API_KEY_SUMMARY")
        if not main_key or not summary_key:
            raise RuntimeError(
                "GEMINI_API_KEY_MAIN and GEMINI_API_KEY_SUMMARY must be set"
            )

        model_name = model or os.environ.get("GEMINI_MODEL", "gemini-1.5-pro")
        self.main_llm = ChatGoogleGenerativeAI(
            model=model_name, google_api_key=main_key
        )
        self.summary_llm = ChatGoogleGenerativeAI(
            model=model_name, google_api_key=summary_key
        )

        self.max_token_limit = max_token_limit
        self.chains: Dict[str, ConversationChain] = {}

        # 会話時に使用する共通プロンプト
        self.prompt = ChatPromptTemplate.from_messages(
            [
                ("system", self.system_prompt),
                MessagesPlaceholder("history"),
                ("human", "{input}"),
            ]
        )

    def _get_chain(self, session_id: str) -> ConversationChain:
        """チャンネル / DM ごとのチェーンを取得。"""

        if session_id not in self.chains:
            memory = ConversationSummaryBufferMemory(
                llm=self.summary_llm,
                max_token_limit=self.max_token_limit,
                return_messages=True,
                memory_key="history",
            )
            self.chains[session_id] = ConversationChain(
                llm=self.main_llm,
                memory=memory,
                prompt=self.prompt,
                verbose=False,
            )
        return self.chains[session_id]

    def respond(self, message: str, session_id: str) -> str:
        """入力メッセージに応答を生成する。"""

        if not message or not message.strip():
            return "ご用件を一言で教えてください。"

        chain = self._get_chain(session_id)
        try:
            return chain.predict(input=message.strip())
        except Exception as e:  # pragma: no cover - best effort
            # Slack で黙らないためのフォールバック
            return (
                "エラーが発生しました。少し時間をおいて再試行してください。"
                f"（詳細: {type(e).__name__})"
            )

