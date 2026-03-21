"""
Approval model — queue of actions awaiting human authorization.
"""
from sqlalchemy import Column, String, Integer, Text, JSON
from .base import Base, TimestampMixin, new_uuid


class ApprovalModel(Base, TimestampMixin):
    __tablename__ = "approvals"

    id          = Column(String(36), primary_key=True, default=new_uuid)
    task_id     = Column(String(36), nullable=True,  index=True)
    action      = Column(String(80), nullable=False)
    details     = Column(JSON,       nullable=True)
    risk_level  = Column(Integer,    nullable=False)
    status      = Column(String(40), nullable=False, default="pending")
    # status: pending | approved | denied | expired
    requested_by = Column(String(80), nullable=True)
    resolved_by  = Column(String(80), nullable=True)
    resolved_at  = Column(String(40), nullable=True)
    note         = Column(Text,       nullable=True)
