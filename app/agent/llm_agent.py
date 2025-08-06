import os
from openai import OpenAI

from .base_agent import BaseAgent


class LLMAgent(BaseAgent):
    """Agent that generates responses using an OpenAI model."""

    def __init__(self, name: str = "LLMAgent") -> None:
        super().__init__(name)
        api_key = os.environ.get("OPENAI_API_KEY")
        self.client = OpenAI(api_key=api_key) if api_key else OpenAI()

    def respond(self, message: str) -> str:
        completion = self.client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {
                    "role": "system",
                    "content": "You are a helpful assistant responding in Japanese.",
                },
                {"role": "user", "content": message},
            ],
        )
        return completion.choices[0].message["content"].strip()
