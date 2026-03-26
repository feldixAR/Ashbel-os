"""
Lead (CRM) and LeadHistory models.
"""
from sqlalchemy import (
    Column, String, Integer, Float, Text,
    ForeignKey, JSON
)
from sqlalchemy.orm import relationship
from .base import Base, TimestampMixin, new_uuid


class LeadModel(Base, TimestampMixin):
    __tablename__ = "leads"

    id            = Column(String(36),  primary_key=True, default=new_uuid)
    name          = Column(String(200),  nullable=False)   # supports Unicode (Hebrew, Arabic, etc.)
    city          = Column(String(120),  nullable=True)
    phone         = Column(String(40),   nullable=True, index=True)
    email         = Column(String(200),  nullable=True)
    sector        = Column(String(80),   nullable=True, index=True)  # e.g. "aluminum", "dj", "real_estate"
    source        = Column(String(60),   nullable=False, default="manual", index=True)
    status        = Column(String(60),   nullable=False, default="חדש", index=True)
    score         = Column(Integer,      nullable=False, default=0, index=True)
    attempts      = Column(Integer,      nullable=False, default=0)
    last_contact  = Column(String(40),   nullable=True)
    response      = Column(Text,         nullable=True)
    notes         = Column(Text,         nullable=True)
    assigned_agent_id = Column(String(36), nullable=True)

    history = relationship("LeadHistoryModel",
                           back_populates="lead",
                           cascade="all, delete-orphan",
                           order_by="LeadHistoryModel.created_at")

    def __repr__(self) -> str:
        return f"<Lead {self.name} [{self.status}] score={self.score}>"


class LeadHistoryModel(Base):
    """Append-only interaction log per lead."""
    __tablename__ = "lead_history"

    id        = Column(String(36), primary_key=True, default=new_uuid)
    lead_id   = Column(String(36), ForeignKey("leads.id"), nullable=False, index=True)
    action    = Column(String(120), nullable=False)
    note      = Column(Text,        nullable=True)
    agent_id  = Column(String(36),  nullable=True)
    model_used= Column(String(60),  nullable=True)
    created_at= Column(String(40),  nullable=False)

    lead = relationship("LeadModel", back_populates="history")
