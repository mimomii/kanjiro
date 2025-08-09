"""飲食店の検索と予約準備を担当するエージェント。"""

from .llm_agent import LLMAgent


class KennsakuKennsakuAgent(LLMAgent):
    """指示に基づき飲食店を検索する。"""

    def __init__(self) -> None:
        # 都内の飲食店を条件に合わせて検索し候補を提示するプロンプトを設定
        super().__init__(
            name="KennsakuKennsakuAgent",
            system_prompt=(
                "あなたは『検索検索』エージェントです。与えられた条件から都内の"\
                "飲食店を検索し、候補を日本語で提示してください。"
            ),
        )

