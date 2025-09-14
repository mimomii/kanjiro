"""Gemini ベースの会話エージェント。

Slack での会話ごとにメモリを保持するため、`ConversationBufferMemory` と
ローリング要約を組み合わせた `ConversationSummaryBufferMemory` を用いて
コンテキストを管理する。応答生成と要約には別々の Gemini API キーを
使用する。
"""

from __future__ import annotations

import os
from typing import Optional

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

        model_name = model or os.environ.get("GEMINI_MODEL", "gemini-2.5-flash-lite")
        self.main_llm = ChatGoogleGenerativeAI(
            model=model_name, google_api_key=main_key
        )
        self.summary_llm = ChatGoogleGenerativeAI(
            model=model_name, google_api_key=summary_key
        )

        self.max_token_limit = max_token_limit
        self.chain: Optional[ConversationChain] = None
        self._memory: Optional[ConversationSummaryBufferMemory] = None

        # 会話時に使用する共通プロンプト
        self.prompt = ChatPromptTemplate.from_messages(
            [
                ("system", self.system_prompt),
                MessagesPlaceholder("history"),
                ("human", "{input}"),
            ]
        )

    def _get_chain(self) -> ConversationChain:
        """単一チャンネル用のチェーンを返す。"""

        if self.chain is None:
            self._memory = ConversationSummaryBufferMemory(
                llm=self.summary_llm,
                max_token_limit=self.max_token_limit,
                return_messages=True,
                memory_key="history",
            )
            self.chain = ConversationChain(
                llm=self.main_llm,
                memory=self._memory,
                prompt=self.prompt,
                verbose=False,
            )
        return self.chain

    def _get_memory(self) -> ConversationSummaryBufferMemory:
        """内部メモリへのアクセス（未初期化なら初期化）。"""
        if self._memory is None:
            _ = self._get_chain()
        return self._memory  # type: ignore[return-value]

    def remember(self, text: str, as_user: bool = True) -> None:
        """
        返信せずに“記憶だけ”を積む。@なしの発話や雑談を受動インジェストする用途。
        """
        if not text or not text.strip():
            return
        mem = self._get_memory()
        if as_user:
            mem.chat_memory.add_user_message(text.strip())
        else:
            mem.chat_memory.add_ai_message(text.strip())

    def respond(self, message: str) -> str:
        """入力メッセージに応答を生成する。"""

        if not message or not message.strip():
            return "ご用件を一言で教えてください。"

        try:
            return self._get_chain().predict(input=message.strip())
        except Exception as e:
            return (
                "エラーが発生しました。少し時間をおいて再試行してください。"
                f"（詳細: {type(e).__name__})"
            )

    def get_summary(self, max_chars: int = 600) -> str:
        """会話の要約（あれば）を返す。無ければ直近履歴をざっくり連結。"""
        mem = self._get_memory()
        # LangChainの実装差異吸収
        summary = getattr(mem, "buffer", "") or getattr(mem, "moving_summary_buffer", "")
        if isinstance(summary, str) and summary.strip():
            return summary[:max_chars]
        try:
            vars = mem.load_memory_variables({})
            history = vars.get("history", [])
            if isinstance(history, list):
                lines = []
                for m in history[-10:]:
                    role = getattr(m, "type", None) or getattr(m, "role", None) or "msg"
                    content = getattr(m, "content", "") or ""
                    if content:
                        lines.append(f"{role}: {content}")
                return "\n".join(lines)[:max_chars] if lines else ""
        except Exception:
            pass
        return ""
