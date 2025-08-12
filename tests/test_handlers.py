import importlib
import os


class DummyApp:
    def __init__(self, *args, **kwargs):
        pass

    def event(self, *args, **kwargs):
        def decorator(func):
            return func

        return decorator

    command = view = action = event


def test_strip_mention(monkeypatch):
    monkeypatch.setenv("SLACK_BOT_TOKEN", "x")
    monkeypatch.setenv("SLACK_APP_TOKEN", "x")
    monkeypatch.setenv("GEMINI_API_KEY_MAIN", "x")
    monkeypatch.setenv("GEMINI_API_KEY_SUMMARY", "x")
    monkeypatch.setenv("HOTPEPPER_API_KEY", "x")
    monkeypatch.setattr("slack_bolt.App", DummyApp)
    main = importlib.reload(importlib.import_module("main"))
    assert main._strip_mention("<@U123> hello") == "hello"
    assert main._strip_mention("no mention") == "no mention"
