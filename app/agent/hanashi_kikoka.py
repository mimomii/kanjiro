"""DMで参加者と個別に会話するエージェント。"""

from .llm_agent import LLMAgent


class HanashiKikokaAgent(LLMAgent):
    """個人チャットで各参加者へのフォローを行う。"""

    def __init__(self) -> None:
        # 各参加者とのDMで丁寧な聞き取りを行うプロンプトを設定
        super().__init__(
            name="HanashiKikokaAgent",
            system_prompt=(
                "あなたは『話し聞こか』エージェントです。参加者の個人チャットで"\
                "希望や懸念を丁寧にヒアリングし、日本語で応答してください。"
            ),
        )

