import os
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from dotenv import load_dotenv

load_dotenv()
app = App(token=os.environ.get("SLACK_BOT_TOKEN"))

@app.event("app_mention")
def handle_mention(event, say):
    user = event["user"]
    say(f"<@{user}> 幹事郎が参上しました！ご用件はなんでしょうか？")

if __name__ == "__main__":
    handler = SocketModeHandler(app, os.environ.get("SLACK_BOT_TOKEN"))
    handler.start()
