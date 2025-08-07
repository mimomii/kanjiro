"""グループチャットを主導するエージェント。"""

from .llm_agent import LLMAgent


class ShikiriTagariAgent(LLMAgent):
    """グループチャットを進行し最終提案を行う。"""

    def __init__(self) -> None:
        # 全体の計画を調整し最終的な場所と日時を提案するプロンプトを設定
        super().__init__(
            name="ShikiriTagariAgent",
            system_prompt=(
                "あなたは幹事AI『仕切りたがり』です。参加者の希望を整理し、"\
                "都内での飲み会の場所・日時・お店を提案してください。"
            ),
        )

