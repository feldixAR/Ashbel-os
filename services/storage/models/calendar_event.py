"""
CalendarEventModel — meetings, demos, calls and follow-ups.
event_type: meeting | call | followup | demo | site_visit
status:     scheduled | completed | cancelled | no_show
"""
from sqlalchemy import Column, String, Text
from .base import Base, TimestampMixin, new_uuid


class CalendarEventModel(Base, TimestampMixin):
    __tablename__ = "calendar_events"

    id           = Column(String(36),  primary_key=True, default=new_uuid)
    lead_id      = Column(String(36),  nullable=False, index=True)
    deal_id      = Column(String(36),  nullable=True)
    title        = Column(String(200), nullable=False)
    event_type   = Column(String(30),  nullable=False, default="meeting", index=True)
    starts_at_il = Column(String(40),  nullable=False)   # ISO-8601 Asia/Jerusalem
    ends_at_il   = Column(String(40),  nullable=True)
    location     = Column(String(200), nullable=True)
    notes        = Column(Text,        nullable=True)
    status       = Column(String(20),  nullable=False, default="scheduled", index=True)
    created_by   = Column(String(120), nullable=True)

    def to_dict(self) -> dict:
        return {
            "id":           self.id,
            "lead_id":      self.lead_id,
            "deal_id":      self.deal_id,
            "title":        self.title,
            "event_type":   self.event_type,
            "starts_at_il": self.starts_at_il,
            "ends_at_il":   self.ends_at_il,
            "location":     self.location,
            "notes":        self.notes,
            "status":       self.status,
            "created_by":   self.created_by,
            "created_at":   str(self.created_at) if self.created_at else None,
        }
