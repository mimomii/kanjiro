import os

from dotenv import load_dotenv
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

from app.agent.llm_agent import LLMAgent

load_dotenv()

app = App(token=os.environ.get("SLACK_BOT_TOKEN"))
llm_agent = LLMAgent()


@app.event("app_mention")
def handle_mention(event, say):
    """Respond to mentions with an LLM-generated message."""
    user = event["user"]
    # Remove the mention from the incoming text
    text = event.get("text", "")
    prompt = text.split("<@", 1)[-1]
    prompt = prompt.split(">", 1)[-1].strip()
    response = llm_agent.respond(prompt)
    say(f"<@{user}> {response}")


if __name__ == "__main__":
    handler = SocketModeHandler(app, os.environ.get("SLACK_APP_TOKEN"))
    handler.start()
