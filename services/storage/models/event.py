"""
Event model — append-only event log. Never updated, only inserted.
"""
from sqlalchemy import Column, String, Text, JSON
from .base import Base, new_uuid


class EventModel(Base):
    """
    Append-only. No TimestampMixin (updated_at irrelevant here).
    created_at stored as ISO string for portability.
    """
    __tablename__ = "events"

    id              = Column(String(36),  primary_key=True, default=new_uuid)
    event_type      = Column(String(80),  nullable=False, index=True)
    payload         = Column(JSON,        nullable=True)
    source_agent_id = Column(String(36),  nullable=True, index=True)
    source_task_id  = Column(String(36),  nullable=True, index=True)
    trace_id        = Column(String(36),  nullable=True, index=True)
    created_at      = Column(String(40),  nullable=False, index=True)

    def __repr__(self) -> str:
        return f"<Event {self.event_type} @ {self.created_at}>"
