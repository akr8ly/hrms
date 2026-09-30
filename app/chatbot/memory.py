import re
import threading
from collections import deque
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Literal
from uuid import uuid4

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage

from app.chatbot.config import chatbot_settings


MessageRole = Literal["user", "assistant"]
SENSITIVE_PATTERNS = (
    re.compile(r"authorization\s*:\s*bearer\s+\S+", re.IGNORECASE),
    re.compile(r"bearer\s+eyJ[\w.-]+", re.IGNORECASE),
    re.compile(
        r"(?:password|security_answer|pii_key|api_key|access_token)"
        r"\s*[:=]\s*\S+",
        re.IGNORECASE,
    ),
)


class SessionNotFoundError(KeyError):
    pass


class SessionAccessError(PermissionError):
    pass


class SensitiveMemoryError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class MemoryMessage:
    role: MessageRole
    content: str
    created_at: datetime


@dataclass(slots=True)
class ChatSession:
    session_id: str
    user_id: int
    user_role: str
    created_at: datetime
    expires_at: datetime
    messages: deque[MemoryMessage] = field(default_factory=deque)


class SessionMemoryStore:
    def __init__(self) -> None:
        self._sessions: dict[str, ChatSession] = {}
        self._lock = threading.RLock()

    def create_session(self, *, user_id: int, user_role: str) -> str:
        if user_id <= 0:
            raise ValueError("user_id must be positive")
        cleaned_role = user_role.strip().lower()
        if not cleaned_role:
            raise ValueError("user_role cannot be empty")

        now = datetime.now(UTC)
        session_id = str(uuid4())
        session = ChatSession(
            session_id=session_id,
            user_id=user_id,
            user_role=cleaned_role,
            created_at=now,
            expires_at=now + timedelta(
                minutes=chatbot_settings.session_ttl_minutes
            ),
            messages=deque(maxlen=chatbot_settings.max_history),
        )
        with self._lock:
            self._remove_expired(now)
            self._sessions[session_id] = session
        return session_id

    def add_message(
        self,
        *,
        session_id: str,
        user_id: int,
        role: MessageRole,
        content: str,
    ) -> None:
        cleaned_content = content.strip()
        if not cleaned_content:
            raise ValueError("Memory message cannot be empty")
        if len(cleaned_content) > chatbot_settings.max_memory_message_length:
            raise ValueError("Memory message exceeds the configured length limit")
        if any(pattern.search(cleaned_content) for pattern in SENSITIVE_PATTERNS):
            raise SensitiveMemoryError(
                "Authentication credentials and secrets cannot be stored in memory"
            )

        now = datetime.now(UTC)
        with self._lock:
            session = self._get_owned_session(session_id, user_id, now)
            session.messages.append(
                MemoryMessage(role=role, content=cleaned_content, created_at=now)
            )
            session.expires_at = now + timedelta(
                minutes=chatbot_settings.session_ttl_minutes
            )

    def get_history(
        self,
        *,
        session_id: str,
        user_id: int,
    ) -> list[MemoryMessage]:
        now = datetime.now(UTC)
        with self._lock:
            session = self._get_owned_session(session_id, user_id, now)
            session.expires_at = now + timedelta(
                minutes=chatbot_settings.session_ttl_minutes
            )
            return list(session.messages)

    def get_langchain_history(
        self,
        *,
        session_id: str,
        user_id: int,
    ) -> list[BaseMessage]:
        history = self.get_history(session_id=session_id, user_id=user_id)
        return [
            HumanMessage(content=message.content)
            if message.role == "user"
            else AIMessage(content=message.content)
            for message in history
        ]

    def clear_session(self, *, session_id: str, user_id: int) -> None:
        now = datetime.now(UTC)
        with self._lock:
            self._get_owned_session(session_id, user_id, now)
            del self._sessions[session_id]

    def _get_owned_session(
        self,
        session_id: str,
        user_id: int,
        now: datetime,
    ) -> ChatSession:
        self._remove_expired(now)
        session = self._sessions.get(session_id)
        if session is None:
            raise SessionNotFoundError("Chat session was not found or has expired")
        if session.user_id != user_id:
            raise SessionAccessError("Chat session belongs to another user")
        return session

    def _remove_expired(self, now: datetime) -> None:
        expired_ids = [
            session_id
            for session_id, session in self._sessions.items()
            if session.expires_at <= now
        ]
        for session_id in expired_ids:
            del self._sessions[session_id]


session_memory = SessionMemoryStore()
