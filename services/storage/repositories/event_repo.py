"""Event repository — append-only."""
from typing import List, Optional
from services.storage.db import get_session
from services.storage.models.event import EventModel
from .base_repo import utcnow_iso


class EventRepository:
    """No BaseRepository — events are never updated or deleted."""

    def append(self, event_type: str, payload: dict = None,
                source_agent_id: str = None,
                source_task_id:  str = None,
                trace_id:        str = None) -> EventModel:
        from services.storage.models.base import new_uuid
        event = EventModel(
            id=new_uuid(),
            event_type=event_type,
            payload=payload or {},
            source_agent_id=source_agent_id,
            source_task_id=source_task_id,
            trace_id=trace_id,
            created_at=utcnow_iso(),
        )
        with get_session() as s:
            s.add(event)
        return event

    def get_by_type(self, event_type: str, limit: int = 100) -> List[EventModel]:
        with get_session() as s:
            return (s.query(EventModel)
                    .filter_by(event_type=event_type)
                    .order_by(EventModel.created_at.desc())
                    .limit(limit)
                    .all())

    def get_recent(self, limit: int = 50) -> List[EventModel]:
        with get_session() as s:
            return (s.query(EventModel)
                    .order_by(EventModel.created_at.desc())
                    .limit(limit)
                    .all())

    def get_by_trace(self, trace_id: str) -> List[EventModel]:
        with get_session() as s:
            return (s.query(EventModel)
                    .filter_by(trace_id=trace_id)
                    .order_by(EventModel.created_at)
                    .all())
