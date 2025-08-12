import os, sys, time

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from app.state.session_store import SessionStore
from app.models.events import EventContext


def make_ctx():
    return EventContext(
        channel="C",
        thread_ts="T",
        organizer="U",
        date_candidates=[],
        start_time_range="",
        area_text="",
        genre_candidates=[],
        must_haves={},
        budget_min=None,
        budget_max=None,
        participants=[],
    )


def test_session_store_ttl_and_lru():
    store = SessionStore(maxsize=2, ttl=1)
    ctx = make_ctx()
    store.set("a", ctx)
    assert store.get("a") is ctx
    time.sleep(1.2)
    assert store.get("a") is None  # expired
    store.set("a", ctx)
    store.set("b", ctx)
    store.set("c", ctx)  # should evict 'a'
    assert store.get("a") is None
    assert store.get("b") is not None
