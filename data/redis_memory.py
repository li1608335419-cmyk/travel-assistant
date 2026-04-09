import os
import uuid
from datetime import UTC, datetime
from typing import Any, Dict, Optional

import redis

from models.schemas import Message, SessionState, StructuredTripRequest


class RedisUnavailableError(RuntimeError):
    pass


class RedisMemoryStore:
    def __init__(
        self,
        client: Optional[redis.Redis] = None,
        prefix: str = "travel:session:",
        ttl_seconds: Optional[int] = None,
        max_history: Optional[int] = None,
    ) -> None:
        self.prefix = prefix
        self.ttl_seconds = ttl_seconds or int(os.getenv("SESSION_TTL_MINUTES", "60")) * 60
        self.max_history = max_history or int(os.getenv("MAX_HISTORY_MESSAGES", "12"))
        self.client = client or redis.Redis(
            host=os.getenv("REDIS_HOST", "localhost"),
            port=int(os.getenv("REDIS_PORT", "6379")),
            db=int(os.getenv("REDIS_DB", "0")),
            password=os.getenv("REDIS_PASSWORD") or None,
            decode_responses=True,
            socket_connect_timeout=5,
        )
        self._assert_connected()

    def _assert_connected(self) -> None:
        try:
            self.client.ping()
        except redis.RedisError as exc:
            raise RedisUnavailableError("Redis is required for short-term memory.") from exc

    def _key(self, session_id: str) -> str:
        return f"{self.prefix}{session_id}"

    def create_session(self, user_id: str, session_id: Optional[str] = None) -> SessionState:
        session_id = session_id or f"SESSION-{uuid.uuid4().hex[:10].upper()}"
        state = SessionState(session_id=session_id, user_id=user_id)
        self.save_session(state)
        return state

    def get_session(self, session_id: str) -> Optional[SessionState]:
        raw = self.client.get(self._key(session_id))
        if raw is None:
            return None
        self.client.expire(self._key(session_id), self.ttl_seconds)
        return SessionState.model_validate_json(raw)

    def save_session(self, state: SessionState) -> SessionState:
        state.updated_at = datetime.now(UTC)
        self.client.set(self._key(state.session_id), state.model_dump_json(), ex=self.ttl_seconds)
        return state

    def require_session(self, user_id: str, session_id: Optional[str]) -> SessionState:
        if session_id:
            existing = self.get_session(session_id)
            if existing:
                return existing
        return self.create_session(user_id=user_id, session_id=session_id)

    def add_message(self, session_id: str, message: Message) -> SessionState:
        state = self.get_session(session_id)
        if state is None:
            raise KeyError(f"Unknown session: {session_id}")
        state.messages.append(message)
        if len(state.messages) > self.max_history:
            state.messages = state.messages[-self.max_history :]
        return self.save_session(state)

    def update_profile(self, session_id: str, patch: Dict[str, Any]) -> SessionState:
        state = self.get_session(session_id)
        if state is None:
            raise KeyError(f"Unknown session: {session_id}")
        profile = state.trip_profile.model_dump()
        for key, value in patch.items():
            if value is not None and key in profile:
                profile[key] = value
        state.trip_profile = StructuredTripRequest.model_validate(profile)
        return self.save_session(state)

    def update_summary(self, session_id: str, summary: str) -> SessionState:
        state = self.get_session(session_id)
        if state is None:
            raise KeyError(f"Unknown session: {session_id}")
        state.summary = summary
        return self.save_session(state)

    def remember_tool_result(self, session_id: str, tool_name: str, payload: Dict[str, Any]) -> SessionState:
        state = self.get_session(session_id)
        if state is None:
            raise KeyError(f"Unknown session: {session_id}")
        state.tool_memory[tool_name] = {
            "payload": payload,
            "saved_at": datetime.now(UTC).isoformat(),
        }
        return self.save_session(state)

    def delete_session(self, session_id: str) -> bool:
        return bool(self.client.delete(self._key(session_id)))
