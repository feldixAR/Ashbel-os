"""
Dead Letter Queue model — failed tasks that exhausted retries.
"""
from sqlalchemy import Column, String, Integer, Text, JSON
from .base import Base, TimestampMixin, new_uuid


class DLQModel(Base, TimestampMixin):
    __tablename__ = "dlq"

    id              = Column(String(36), primary_key=True, default=new_uuid)
    original_task_id= Column(String(36), nullable=False, index=True)
    action          = Column(String(80), nullable=False)
    payload         = Column(JSON,       nullable=True)
    failure_reason  = Column(Text,       nullable=False)
    attempts_made   = Column(Integer,    nullable=False, default=0)
    status          = Column(String(40), nullable=False, default="pending_review")
    # status: pending_review | manually_resolved | discarded | replayed
    resolved_at     = Column(String(40), nullable=True)
    resolved_note   = Column(Text,       nullable=True)
