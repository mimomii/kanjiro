"""In-memory store for EventContext objects with TTL and LRU eviction."""

from __future__ import annotations

import time
from collections import OrderedDict
from typing import Dict, Optional

from app.models.events import EventContext


class SessionStore:
    """Simple in-memory session store.

    The store keeps session data for each Slack thread. It uses TTL to expire
    old sessions and an LRU policy to cap memory usage. This is intentionally
    lightweight so that it can later be swapped out with Redis or SQLite.
    """

    def __init__(self, maxsize: int = 128, ttl: int = 60 * 60) -> None:
        self.maxsize = maxsize
        self.ttl = ttl
        self._data: "OrderedDict[str, tuple[EventContext, float]]" = OrderedDict()

    def _evict_expired(self) -> None:
        now = time.time()
        expired = [sid for sid, (_, ts) in self._data.items() if now - ts > self.ttl]
        for sid in expired:
            self._data.pop(sid, None)

    def get(self, session_id: str) -> Optional[EventContext]:
        """Return the context for ``session_id`` if it exists and is fresh."""

        self._evict_expired()
        item = self._data.get(session_id)
        if not item:
            return None
        ctx, _ = item
        # mark as recently used
        self._data.move_to_end(session_id)
        self._data[session_id] = (ctx, time.time())
        return ctx

    def set(self, session_id: str, ctx: EventContext) -> None:
        """Store context for ``session_id``."""

        self._evict_expired()
        if session_id in self._data:
            self._data.move_to_end(session_id)
        self._data[session_id] = (ctx, time.time())
        # LRU eviction
        if len(self._data) > self.maxsize:
            self._data.popitem(last=False)

    def evict(self, session_id: str) -> None:
        """Remove ``session_id`` from the store if present."""

        self._data.pop(session_id, None)
