"""
LeadDiscovery — discovery session model.
Tracks each run of the lead acquisition engine.
Phase 12: Lead Acquisition OS
"""
from sqlalchemy import Column, String, Integer, Text
from .base import Base, TimestampMixin, new_uuid


class LeadDiscoveryModel(Base, TimestampMixin):
    __tablename__ = "lead_discoveries"

    id                = Column(String(36),  primary_key=True, default=new_uuid)
    session_id        = Column(String(40),  nullable=False, unique=True, index=True)
    goal              = Column(Text,        nullable=False)
    segments_json     = Column(Text,        nullable=True)
    source_types_json = Column(Text,        nullable=True)
    lead_count        = Column(Integer,     nullable=False, default=0)
    status            = Column(String(30),  nullable=False, default="running")  # running|completed|failed

    def __repr__(self):
        return f"<LeadDiscovery {self.session_id} leads={self.lead_count}>"
