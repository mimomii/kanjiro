from .base_agent import BaseAgent

class HanashiKikokaAgent(BaseAgent):
    def respond(self, message: str) -> str:
        return "なるほど、つまりこういう話ですね。整理してみます。"
