"""
OutreachModel — persists outreach records per goal/opportunity.
Batch 6: Goal & Growth Engine.
Batch 8: Dispatch tracking columns.
Batch 9: Lifecycle FSM columns + threading (parent_record_id).
"""
from sqlalchemy import Column, String, Text, Integer
from .base import Base, TimestampMixin, new_uuid


class OutreachModel(Base, TimestampMixin):
    __tablename__ = "outreach_records"

    id                  = Column(String(36),  primary_key=True, default=new_uuid)
    goal_id             = Column(String(36),  nullable=False, index=True)
    opp_id              = Column(String(36),  nullable=True)
    contact_name        = Column(String(120), nullable=False)
    contact_phone       = Column(String(40),  nullable=True)
    channel             = Column(String(40),  nullable=False, default="whatsapp")
    message_body        = Column(Text,        nullable=True)
    # Dispatch status (ready → sent | failed)
    status              = Column(String(30),  nullable=False, default="pending", index=True)
    attempt             = Column(Integer,     nullable=False, default=1)
    sent_at             = Column(String(40),  nullable=True)   # ISO-8601, Asia/Jerusalem
    replied_at          = Column(String(40),  nullable=True)
    next_followup       = Column(String(40),  nullable=True)
    notes               = Column(Text,        nullable=True)
    # Batch 8 — dispatch tracking
    delivery_status     = Column(String(40),  nullable=True)   # delivered | failed | pending_ack
    failure_reason      = Column(Text,        nullable=True)
    provider_message_id = Column(String(80),  nullable=True)   # Telegram message_id
    # Batch 9 — lifecycle FSM
    parent_record_id    = Column(String(36),  nullable=True, index=True)
    # sent | awaiting_response | followup_due | followup_sent | closed_won | closed_lost
    lifecycle_status    = Column(String(30),  nullable=False, default="sent", index=True)
    next_action_at      = Column(String(40),  nullable=True)   # ISO-8601, Asia/Jerusalem

    def to_dict(self) -> dict:
        return {
            "id":                  self.id,
            "goal_id":             self.goal_id,
            "opp_id":              self.opp_id,
            "contact_name":        self.contact_name,
            "contact_phone":       self.contact_phone,
            "channel":             self.channel,
            "message_body":        self.message_body,
            "status":              self.status,
            "attempt":             self.attempt,
            "sent_at":             self.sent_at,
            "replied_at":          self.replied_at,
            "next_followup":       self.next_followup,
            "notes":               self.notes,
            "delivery_status":     self.delivery_status,
            "failure_reason":      self.failure_reason,
            "provider_message_id": self.provider_message_id,
            "parent_record_id":    self.parent_record_id,
            "lifecycle_status":    self.lifecycle_status,
            "next_action_at":      self.next_action_at,
            "created_at":          str(self.created_at) if self.created_at else None,
        }
