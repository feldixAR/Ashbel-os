"""
Agent and AgentVersion models.
"""
import datetime
from sqlalchemy import (
    Column, String, Integer, Boolean, Text,
    Float, ForeignKey, JSON
)
from sqlalchemy.orm import relationship
from .base import Base, TimestampMixin, new_uuid


class AgentModel(Base, TimestampMixin):
    __tablename__ = "agents"

    id                = Column(String(36),  primary_key=True, default=new_uuid)
    name              = Column(String(120),  nullable=False)
    role              = Column(String(120),  nullable=False)
    department        = Column(String(80),   nullable=False, index=True)
    active_version    = Column(Integer,      nullable=False, default=1)
    model_preference  = Column(String(60),   nullable=False, default="claude_haiku")
    risk_tolerance    = Column(Integer,      nullable=False, default=2)
    capabilities      = Column(JSON,         nullable=False, default=list)
    active            = Column(Boolean,      nullable=False, default=True, index=True)
    tasks_done        = Column(Integer,      nullable=False, default=0)
    last_active_at    = Column(String(40),   nullable=True)

    versions          = relationship("AgentVersionModel",
                                     back_populates="agent",
                                     cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Agent {self.name} [{self.department}] v{self.active_version}>"


class AgentVersionModel(Base, TimestampMixin):
    __tablename__ = "agent_versions"

    id                = Column(String(36),  primary_key=True, default=new_uuid)
    agent_id          = Column(String(36),  ForeignKey("agents.id"), nullable=False, index=True)
    version           = Column(Integer,     nullable=False)
    system_prompt     = Column(Text,        nullable=False)
    model_preference  = Column(String(60),  nullable=False)
    is_active         = Column(Boolean,     nullable=False, default=False)

    # Performance metrics accumulated for this version
    tasks_executed      = Column(Integer, nullable=False, default=0)
    success_rate        = Column(Float,   nullable=True)
    avg_quality_score   = Column(Float,   nullable=True)
    avg_latency_ms      = Column(Float,   nullable=True)
    avg_cost_usd        = Column(Float,   nullable=True)

    active_from         = Column(String(40), nullable=True)
    active_until        = Column(String(40), nullable=True)

    agent = relationship("AgentModel", back_populates="versions")

    def __repr__(self) -> str:
        return f"<AgentVersion agent={self.agent_id} v={self.version} active={self.is_active}>"
