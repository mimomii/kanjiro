"""会話の文脈を解析し、他のエージェントへ指示を出すエージェント。"""

from .llm_agent import LLMAgent


class ReadAirAgent(LLMAgent):
    """全てのメッセージをこっそり読み、他のエージェントを指揮する。"""

    def __init__(self) -> None:
        # 会話を解析して他エージェントへ簡潔な指示を出すプロンプトを設定
        super().__init__(
            name="ReadAirAgent",
            system_prompt=(
                "あなたは『空気読み』エージェントです。会話全体を把握し、"\
                "他のエージェントへの簡潔な指示を日本語で出してください。"
            ),
        )

