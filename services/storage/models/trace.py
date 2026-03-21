"""
Trace model — full execution trace per command/task.
"""
from sqlalchemy import Column, String, Integer, JSON
from .base import Base, new_uuid


class TraceModel(Base):
    __tablename__ = "traces"

    id         = Column(String(36), primary_key=True, default=new_uuid)
    trace_id   = Column(String(36), nullable=False, unique=True, index=True)
    task_id    = Column(String(36), nullable=True,  index=True)
    command    = Column(String(500), nullable=True)
    spans      = Column(JSON,  nullable=False, default=list)
    duration_ms= Column(Integer, nullable=True)
    status     = Column(String(40), nullable=False, default="open")
    created_at = Column(String(40), nullable=False)
    closed_at  = Column(String(40), nullable=True)
