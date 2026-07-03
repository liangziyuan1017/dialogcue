"""Session store with cap, TTL eviction, and per-session async locks.

F012 Phase C, item 2.2. Replaces the bare `sessions: dict` in server.py so
session memory is bounded and same-session mutations are serialized.
"""

import asyncio
import uuid
from datetime import datetime, timedelta


class SessionStore:
    def __init__(self, max_sessions: int, ttl: int, clock=datetime.now):
        self.max_sessions = int(max_sessions)
        self.ttl = int(ttl)
        self._clock = clock
        self._sessions: dict[str, dict] = {}
        self._locks: dict[str, asyncio.Lock] = {}

    def __len__(self):
        return len(self._sessions)

    def clear(self):
        self._sessions.clear()
        self._locks.clear()

    def create(self, cust_no: str, context: dict) -> str | None:
        session_id = f"sess_{uuid.uuid4().hex[:8]}"
        return self.create_with_id(session_id, cust_no, context)

    def create_with_id(self, session_id: str, cust_no: str, context: dict) -> str | None:
        self.evict_expired()
        if len(self._sessions) >= self.max_sessions:
            self._evict_oldest()
        self._sessions[session_id] = {
            "cust_no": cust_no,
            "context": context,
            "conversation_state": {"branch_key": {}, "inherited_facts": [], "inherited_emotions": [], "willingness": None},
            "conversation_context_buffer": "",
            "transcript": [],
            "start_time": self._clock(),
        }
        self._locks[session_id] = asyncio.Lock()
        return session_id

    def get(self, session_id: str) -> dict | None:
        return self._sessions.get(session_id)

    def remove(self, session_id: str) -> dict | None:
        self._locks.pop(session_id, None)
        return self._sessions.pop(session_id, None)

    def restore(self, session_id: str, session: dict) -> None:
        self.evict_expired()
        if session_id not in self._sessions and len(self._sessions) >= self.max_sessions:
            self._evict_oldest()
        self._sessions[session_id] = session
        self._locks[session_id] = asyncio.Lock()

    def lock(self, session_id: str) -> asyncio.Lock:
        if session_id not in self._locks:
            self._locks[session_id] = asyncio.Lock()
        return self._locks[session_id]

    def evict_expired(self):
        cutoff = self._clock() - timedelta(seconds=self.ttl)
        expired = [sid for sid, s in self._sessions.items() if s["start_time"] < cutoff]
        for sid in expired:
            self.remove(sid)

    def _evict_oldest(self):
        if not self._sessions:
            return
        oldest = min(self._sessions, key=lambda sid: self._sessions[sid]["start_time"])
        self.remove(oldest)
