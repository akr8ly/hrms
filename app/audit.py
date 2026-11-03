"""Persistent, privacy-minimised security audit events."""

from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.models.audit_event import AuditEvent


def record_audit_event(
    db: Session,
    *,
    event_type: str,
    actor_user_id: int | None = None,
    details: dict[str, Any] | None = None,
) -> AuditEvent:
    event = AuditEvent(
        event_type=event_type,
        actor_user_id=actor_user_id,
        details=details or {},
        occurred_at=datetime.now(timezone.utc).replace(tzinfo=None),
    )
    db.add(event)
    return event