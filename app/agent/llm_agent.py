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
            system_prompt
            or (
                "あなたは飲み会の幹事AIです。参加者から不足している情報を"
                "最小限の質問で確認しつつ、3〜5件の候補を提示して次のアクションを"
                "提案してください。すべて日本語で丁寧に応答します。"
            )
        )

        main_key = os.environ.get("GEMINI_API_KEY_MAIN")
        summary_key = os.environ.get("GEMINI_API_KEY_SUMMARY")
        if not main_key or not summary_key:
            raise RuntimeError(
                "GEMINI_API_KEY_MAIN and GEMINI_API_KEY_SUMMARY must be set"
            )

        model_name = model or os.environ.get("GEMINI_MODEL", "gemini-1.5-pro")
        summary_model = os.environ.get(
            "GEMINI_MODEL_SUMMARY", "gemini-1.5-flash"
        )
        self.main_llm = ChatGoogleGenerativeAI(
            model=model_name,
            google_api_key=main_key,
            temperature=0.4,
            max_output_tokens=1024,
            timeout=20,
            max_retries=2,
        )
        self.summary_llm = ChatGoogleGenerativeAI(
            model=summary_model,
            google_api_key=summary_key,
            temperature=0.2,
            max_output_tokens=512,
            timeout=20,
            max_retries=2,
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
        """チャンネルごとのチェーンを取得。"""

        if session_id not in self.chains:
            memory = ConversationSummaryBufferMemory(
                llm=self.summary_llm,
                max_token_limit=self.max_token_limit,
                return_messages=True,
                memory_key="history",
                input_key="input",
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

