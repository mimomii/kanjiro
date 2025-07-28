from .base_agent import BaseAgent

class ShikiriTagariAgent(BaseAgent):
    def respond(self, message: str) -> str:
        return "では、日程候補をいくつか挙げますね！"
