class BaseAgent:
    def __init__(self, name):
        self.name = name

    def respond(self, message: str) -> str:
        raise NotImplementedError("respond メソッドを各エージェントで実装してください")
