"""Durable inbox metadata and execution audit; not a second CRM."""
from sqlalchemy import Column, String, Integer, Text, JSON, UniqueConstraint
from .base import Base, TimestampMixin, new_uuid


class BusinessEventModel(Base, TimestampMixin):
    __tablename__ = 'business_event_inbox'
    __table_args__ = (UniqueConstraint('business_id', 'source', 'source_event_id', name='uq_business_event_source'),)
    id = Column(String(36), primary_key=True, default=new_uuid)
    business_id = Column(String(80), nullable=False, index=True)
    source = Column(String(120), nullable=False)
    source_event_id = Column(String(200), nullable=False)
    event_type = Column(String(80), nullable=False)
    source_ref = Column(Text, nullable=False)
    occurred_at = Column(String(40), nullable=False)
    fingerprint = Column(String(64), nullable=False)
    facts = Column(JSON, nullable=False)
    status = Column(String(40), nullable=False, default='pending', index=True)
    attempts = Column(Integer, nullable=False, default=0)
    lease_token = Column(String(36), nullable=True)
    lease_until = Column(String(40), nullable=True)
    next_attempt_at = Column(String(40), nullable=True)
    last_error_code = Column(String(80), nullable=True)
    trace_id = Column(String(36), nullable=True)
    output = Column(JSON, nullable=True)
