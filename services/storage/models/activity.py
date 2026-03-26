"""
ActivityModel — unified activity log: calls, emails, WhatsApp, meetings, notes.
direction: inbound | outbound
type:      call | email | whatsapp | meeting | note | demo
outcome:   answered | voicemail | no_answer | meeting_booked | proposal_sent |
           deal_won | deal_lost | follow_up_needed | completed
"""
from sqlalchemy import Column, Integer, String, Text
from .base import Base, TimestampMixin, new_uuid

ACTIVITY_TYPES     = ("call", "email", "whatsapp", "meeting", "note", "demo")
ACTIVITY_OUTCOMES  = (
    "answered", "voicemail", "no_answer", "meeting_booked",
    "proposal_sent", "deal_won", "deal_lost", "follow_up_needed", "completed",
)


class ActivityModel(Base, TimestampMixin):
    __tablename__ = "activities"

    id              = Column(String(36),  primary_key=True, default=new_uuid)
    lead_id         = Column(String(36),  nullable=False, index=True)
    deal_id         = Column(String(36),  nullable=True,  index=True)
    activity_type   = Column(String(30),  nullable=False, index=True)   # call/email/...
    direction       = Column(String(10),  nullable=False, default="outbound")  # inbound|outbound
    subject         = Column(String(200), nullable=True)
    notes           = Column(Text,        nullable=True)
    outcome         = Column(String(40),  nullable=True)
    duration_sec    = Column(Integer,     nullable=True)   # for calls
    performed_by    = Column(String(120), nullable=True)   # agent name / "system"
    performed_at_il = Column(String(40),  nullable=True)   # ISO-8601 Asia/Jerusalem

    def to_dict(self) -> dict:
        return {
            "id":              self.id,
            "lead_id":         self.lead_id,
            "deal_id":         self.deal_id,
            "activity_type":   self.activity_type,
            "direction":       self.direction,
            "subject":         self.subject,
            "notes":           self.notes,
            "outcome":         self.outcome,
            "duration_sec":    self.duration_sec,
            "performed_by":    self.performed_by,
            "performed_at_il": self.performed_at_il,
            "created_at":      str(self.created_at) if self.created_at else None,
        }
