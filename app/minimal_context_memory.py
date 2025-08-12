"""Minimal context memory example using Gemini.

This module combines ``ConversationBufferMemory`` with a rolling summary so the
conversation can maintain context without relying on external storage. Two
Gemini API keys are used: one for generating responses and another dedicated to
summarisation.
"""

import os
from typing import List

from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.memory import ConversationSummaryBufferMemory
from langchain.chains import ConversationChain


def build_conversation() -> ConversationChain:
    """Build a conversation chain with rolling summary memory."""
    load_dotenv()

    main_llm = ChatGoogleGenerativeAI(
        model="gemini-pro",
        google_api_key=os.environ["GEMINI_API_KEY_MAIN"],
    )

    summary_llm = ChatGoogleGenerativeAI(
        model="gemini-pro",
        google_api_key=os.environ["GEMINI_API_KEY_SUMMARY"],
    )

    memory = ConversationSummaryBufferMemory(
        llm=summary_llm,
        max_token_limit=1000,
        return_messages=True,
    )

    return ConversationChain(llm=main_llm, memory=memory, verbose=True)


def run_demo(user_inputs: List[str]) -> None:
    """Run a short demonstration conversation."""
    conversation = build_conversation()
    for text in user_inputs:
        reply = conversation.predict(input=text)
        print(f"USER: {text}")
        print(f"BOT: {reply}\n")

    print("---- MEMORY ----")
    # The buffer contains both conversation history and the rolling summary.
    print(conversation.memory.buffer)


if __name__ == "__main__":
    sample_inputs = [
        "こんにちは！今日の天気は？",
        "ありがとう。週末のイベントを教えて。",
        "そのイベントは屋内？チケットいる？",
    ]
    run_demo(sample_inputs)
