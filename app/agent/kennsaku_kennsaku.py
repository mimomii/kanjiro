from .base_agent import BaseAgent

class KennsakuKennsakuAgent(BaseAgent):
    def respond(self, message: str) -> str:
        return "ちょっとお店を検索してみますね。お待ちください。"
