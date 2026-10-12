"""Authenticated REST interface for user-owned chatbot sessions."""

import json
from datetime import datetime
from collections.abc import Iterator

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.chatbot.agent_executor import answer_with_policy_agent
from app.chatbot.config import chatbot_settings
from app.chatbot.memory import (
    SensitiveMemoryError,
    SessionAccessError,
    SessionNotFoundError,
    SessionRoleError,
    create_chat_session,
    session_memory,
)
from app.database import get_db
from app.dependencies import get_current_user
from app.models.role import Role
from app.models.user import User


router = APIRouter(prefix="/chatbot", tags=["Chatbot"])


class ChatSessionRead(BaseModel):
    session_id: str
    user_id: int
    user_role: str
    expires_in_minutes: int


class ChatMessageRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    session_id: str = Field(min_length=36, max_length=36)
    question: str = Field(
        min_length=1,
        max_length=chatbot_settings.max_question_length,
    )


class PolicySourceRead(BaseModel):
    policy_id: str
    title: str
    category: str


class ChatMessageRead(BaseModel):
    answer: str
    sources: list[PolicySourceRead] = Field(default_factory=list)
    tools_used: list[str] = Field(default_factory=list)
    session_id: str


class HistoryMessageRead(BaseModel):
    role: str
    content: str
    created_at: datetime


class ChatHistoryRead(BaseModel):
    session_id: str
    messages: list[HistoryMessageRead]


def _current_role(db: Session, user: User) -> str:
    role = db.get(Role, user.role_id)
    if role is None or role.name not in {"admin", "employee", "query"}:
        raise HTTPException(403, "Your account has no supported chatbot role")
    return role.name


def _translate_session_error(error: Exception) -> HTTPException:
    if isinstance(error, SessionNotFoundError):
        return HTTPException(404, "Chat session was not found or has expired")
    if isinstance(error, (SessionAccessError, SessionRoleError)):
        return HTTPException(403, "You cannot access this chat session")
    if isinstance(error, SensitiveMemoryError):
        return HTTPException(422, str(error))
    return HTTPException(422, str(error))


def _sse_event(event: str, data: object) -> str:
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    return f"event: {event}\ndata: {payload}\n\n"


def _answer_chunks(answer: str) -> Iterator[str]:
    size = chatbot_settings.stream_chunk_size
    for start in range(0, len(answer), size):
        yield answer[start : start + size]


@router.post("/sessions", response_model=ChatSessionRead, status_code=201)
def create_session(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    role = _current_role(db, current_user)
    session_id = create_chat_session(user_id=current_user.id, user_role=role)
    return ChatSessionRead(
        session_id=session_id,
        user_id=current_user.id,
        user_role=role,
        expires_in_minutes=chatbot_settings.session_ttl_minutes,
    )


@router.post("/message", response_model=ChatMessageRead)
def send_message(
    data: ChatMessageRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    role = _current_role(db, current_user)
    try:
        result = answer_with_policy_agent(
            data.question,
            session_id=data.session_id,
            user_id=current_user.id,
            user_role=role,
        )
    except (SessionNotFoundError, SessionAccessError, SessionRoleError) as error:
        raise _translate_session_error(error) from None
    except (SensitiveMemoryError, ValueError) as error:
        raise _translate_session_error(error) from None
    return result


@router.post(
    "/message/stream",
    response_class=StreamingResponse,
    responses={
        200: {
            "description": (
                "Server-Sent Events containing status, token, metadata, "
                "and done events"
            ),
            "content": {"text/event-stream": {}},
        }
    },
)
def stream_message(
    data: ChatMessageRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Stream status and sanitized answer chunks using Server-Sent Events."""
    role = _current_role(db, current_user)
    try:
        session_memory.validate_identity(
            session_id=data.session_id,
            user_id=current_user.id,
            user_role=role,
        )
    except (SessionNotFoundError, SessionAccessError, SessionRoleError) as error:
        raise _translate_session_error(error) from None

    def generate_events() -> Iterator[str]:
        yield _sse_event("status", {"stage": "validating"})
        yield _sse_event("status", {"stage": "processing"})
        try:
            result = answer_with_policy_agent(
                data.question,
                session_id=data.session_id,
                user_id=current_user.id,
                user_role=role,
            )
        except (SensitiveMemoryError, ValueError) as error:
            yield _sse_event("error", {"detail": str(error)})
            return
        except Exception:
            yield _sse_event(
                "error",
                {"detail": "The chatbot could not complete the request"},
            )
            return

        for chunk in _answer_chunks(str(result["answer"])):
            yield _sse_event("token", {"text": chunk})
        yield _sse_event(
            "metadata",
            {
                "session_id": data.session_id,
                "sources": result["sources"],
                "tools_used": result["tools_used"],
            },
        )
        yield _sse_event("done", {"completed": True})

    return StreamingResponse(
        generate_events(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.get(
    "/sessions/{session_id}/history",
    response_model=ChatHistoryRead,
)
def get_session_history(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    role = _current_role(db, current_user)
    try:
        messages = session_memory.get_history(
            session_id=session_id,
            user_id=current_user.id,
            user_role=role,
        )
    except (SessionNotFoundError, SessionAccessError, SessionRoleError) as error:
        raise _translate_session_error(error) from None
    return {
        "session_id": session_id,
        "messages": [
            {
                "role": message.role,
                "content": message.content,
                "created_at": message.created_at,
            }
            for message in messages
        ],
    }


@router.delete("/sessions/{session_id}", status_code=204)
def delete_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    role = _current_role(db, current_user)
    try:
        session_memory.clear_session(
            session_id=session_id,
            user_id=current_user.id,
            user_role=role,
        )
    except (SessionNotFoundError, SessionAccessError, SessionRoleError) as error:
        raise _translate_session_error(error) from None
    return Response(status_code=204)
