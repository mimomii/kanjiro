"""幹事郎の各エージェントをSlackイベントに接続するエントリーポイント。"""

import os

from dotenv import load_dotenv
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

from app.agent import LLMAgent

# 開発時にローカルの .env ファイルから環境変数を読み込む
load_dotenv()

# ボットトークンを使ってSlack Boltアプリを初期化
app = App(token=os.environ.get("SLACK_BOT_TOKEN"))

# Slackへの応答に利用する単一のLLMエージェントを生成
llm_agent = LLMAgent()


@app.event("app_mention")
def handle_mention(event, say):
    """メンションされた際にLLMで生成したメッセージで応答する。"""
    user = event["user"]
    # 受信テキストからメンション部分を取り除き、プロンプトを整形
    text = event.get("text", "")
    prompt = text.split("<@", 1)[-1]
    prompt = prompt.split(">", 1)[-1].strip()

    # 受け取ったメッセージをLLMに渡し、その結果をそのまま返信
    response = llm_agent.respond(prompt)
    say(f"<@{user}> {response}")


@app.event("message")
def handle_dm(event, say):
    """参加者とのダイレクトメッセージに対応する。"""
    if event.get("channel_type") != "im":
        return
    text = event.get("text", "")
    # ダイレクトメッセージでも同様にLLMで応答
    response = llm_agent.respond(text)
    say(response)


if __name__ == "__main__":
    # Socket ModeでSlackアプリを実行し、公開HTTPエンドポイントを不要にする
    handler = SocketModeHandler(app, os.environ.get("SLACK_APP_TOKEN"))
    handler.start()
