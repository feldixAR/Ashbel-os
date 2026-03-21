"""
Task model — full lifecycle tracking with cost and tracing.
"""
from sqlalchemy import Column, String, Integer, Float, Text, JSON
from .base import Base, TimestampMixin, new_uuid


class TaskModel(Base, TimestampMixin):
    __tablename__ = "tasks"

    id              = Column(String(36),  primary_key=True, default=new_uuid)
    type            = Column(String(80),  nullable=False, index=True)
    action          = Column(String(80),  nullable=False)
    priority        = Column(Integer,     nullable=False, default=5)   # 1=highest
    status          = Column(String(40),  nullable=False, default="created", index=True)
    # status values: created | queued | routing | assigned | running |
    #                approval_pending | approved | done | failed | dead_lettered

    agent_id        = Column(String(36),  nullable=True, index=True)
    parent_task_id  = Column(String(36),  nullable=True, index=True)
    trace_id        = Column(String(36),  nullable=True, index=True)

    input_data      = Column(JSON,  nullable=True)
    output_data     = Column(JSON,  nullable=True)

    # Risk & approval
    risk_level      = Column(Integer, nullable=False, default=1)
    approved_by     = Column(String(80), nullable=True)
    approval_id     = Column(String(36), nullable=True)

    # Model usage & cost
    model_used      = Column(String(60),  nullable=True)
    tokens_input    = Column(Integer,     nullable=True)
    tokens_output   = Column(Integer,     nullable=True)
    cost_usd        = Column(Float,       nullable=True)

    # Retry tracking
    retry_count     = Column(Integer, nullable=False, default=0)
    max_retries     = Column(Integer, nullable=False, default=3)
    last_error      = Column(Text,    nullable=True)

    # Timing
    started_at      = Column(String(40), nullable=True)
    completed_at    = Column(String(40), nullable=True)
    duration_ms     = Column(Integer,    nullable=True)

    def __repr__(self) -> str:
        return f"<Task {self.id[:8]} type={self.type} status={self.status}>"
