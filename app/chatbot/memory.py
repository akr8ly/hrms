import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal
from uuid import uuid4

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage

from app.chatbot.config import chatbot_settings
from app.redis_state import get_redis_client, require_redis
from app.security import auth_settings

MessageRole = Literal["user", "assistant"]
SENSITIVE_PATTERNS = (
    re.compile(r"authorization\s*:\s*bearer\s+\S+", re.IGNORECASE),
    re.compile(r"bearer\s+eyJ[\w.-]+", re.IGNORECASE),
    re.compile(r"(?:password|security_answer|pii_key|api_key|access_token)\s*[:=]\s*\S+", re.IGNORECASE),
)


class SessionNotFoundError(KeyError):
    pass


class SessionAccessError(PermissionError):
    pass


class SessionRoleError(PermissionError):
    pass


class SensitiveMemoryError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class MemoryMessage:
    role: MessageRole
    content: str
    created_at: datetime


class RedisChatSessionStore:
    def __init__(self, client=None, *, prefix: str | None = None) -> None:
        self._client = client
        self._prefix = prefix or auth_settings.redis_key_prefix

    @property
    def client(self):
        return self._client or get_redis_client()

    def _session_key(self, session_id: str) -> str:
        return f"{self._prefix}:chat:session:{session_id}"

    def _messages_key(self, session_id: str) -> str:
        return f"{self._prefix}:chat:messages:{session_id}"

    @property
    def _ttl(self) -> int:
        return chatbot_settings.session_ttl_minutes * 60

    def create_session(self, *, user_id: int, user_role: str) -> str:
        if user_id <= 0:
            raise ValueError("user_id must be positive")
        cleaned_role = user_role.strip().lower()
        if not cleaned_role:
            raise ValueError("user_role cannot be empty")
        session_id = str(uuid4())
        payload = json.dumps({
            "user_id": user_id,
            "user_role": cleaned_role,
            "created_at": datetime.now(UTC).isoformat(),
        })
        require_redis(lambda: self.client.set(self._session_key(session_id), payload, ex=self._ttl))
        return session_id

    def add_message(self, *, session_id: str, user_id: int, role: MessageRole, content: str, user_role: str | None = None) -> None:
        cleaned_content = content.strip()
        if not cleaned_content:
            raise ValueError("Memory message cannot be empty")
        if len(cleaned_content) > chatbot_settings.max_memory_message_length:
            raise ValueError("Memory message exceeds the configured length limit")
        if any(pattern.search(cleaned_content) for pattern in SENSITIVE_PATTERNS):
            raise SensitiveMemoryError("Authentication credentials and secrets cannot be stored in memory")
        self._get_owned_session(session_id, user_id, user_role)
        if chatbot_settings.max_history == 0:
            self._touch(session_id)
            return
        message = json.dumps({"role": role, "content": cleaned_content, "created_at": datetime.now(UTC).isoformat()})
        def operation() -> None:
            pipeline = self.client.pipeline(transaction=True)
            pipeline.rpush(self._messages_key(session_id), message)
            pipeline.ltrim(self._messages_key(session_id), -chatbot_settings.max_history, -1)
            pipeline.expire(self._session_key(session_id), self._ttl)
            pipeline.expire(self._messages_key(session_id), self._ttl)
            pipeline.execute()
        require_redis(operation)

    def get_history(self, *, session_id: str, user_id: int, user_role: str | None = None) -> list[MemoryMessage]:
        self._get_owned_session(session_id, user_id, user_role)
        def operation() -> list[str]:
            pipeline = self.client.pipeline(transaction=True)
            pipeline.lrange(self._messages_key(session_id), 0, -1)
            pipeline.expire(self._session_key(session_id), self._ttl)
            pipeline.expire(self._messages_key(session_id), self._ttl)
            return pipeline.execute()[0]
        rows = require_redis(operation)
        return [MemoryMessage(role=item["role"], content=item["content"], created_at=datetime.fromisoformat(item["created_at"])) for row in rows for item in (json.loads(row),)]

    def get_langchain_history(self, *, session_id: str, user_id: int, user_role: str | None = None) -> list[BaseMessage]:
        history = self.get_history(session_id=session_id, user_id=user_id, user_role=user_role)
        return [HumanMessage(content=message.content) if message.role == "user" else AIMessage(content=message.content) for message in history]

    def clear_session(self, *, session_id: str, user_id: int, user_role: str | None = None) -> None:
        self._get_owned_session(session_id, user_id, user_role)
        require_redis(lambda: self.client.delete(self._session_key(session_id), self._messages_key(session_id)))

    def validate_identity(self, *, session_id: str, user_id: int, user_role: str) -> None:
        self._get_owned_session(session_id, user_id, user_role)
        self._touch(session_id)

    def _touch(self, session_id: str) -> None:
        require_redis(lambda: self.client.expire(self._session_key(session_id), self._ttl))

    def _get_owned_session(self, session_id: str, user_id: int, user_role: str | None) -> dict:
        raw = require_redis(lambda: self.client.get(self._session_key(session_id)))
        if raw is None:
            raise SessionNotFoundError("Chat session was not found or has expired")
        try:
            session = json.loads(raw)
        except (TypeError, ValueError) as error:
            raise SessionNotFoundError("Chat session was not found or has expired") from error
        if session.get("user_id") != user_id:
            raise SessionAccessError("Chat session belongs to another user")
        if user_role is not None and session.get("user_role") != user_role.strip().lower():
            raise SessionRoleError("Chat session role no longer matches the user")
        return session


session_memory = RedisChatSessionStore()


def create_chat_session(*, user_id: int, user_role: str) -> str:
    return session_memory.create_session(user_id=user_id, user_role=user_role)