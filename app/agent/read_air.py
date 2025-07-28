from .base_agent import BaseAgent

class ReadAirAgent(BaseAgent):
    def respond(self, message: str) -> str:
        return "その発言、場の空気的にはちょっと微妙かもしれませんね…"
