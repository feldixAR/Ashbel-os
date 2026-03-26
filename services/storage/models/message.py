"""
MessageModel — unified inbound/outbound message store.
Channels: whatsapp | email | sms
Direction: inbound | outbound
Status: sent | delivered | read | failed
"""
from sqlalchemy import Column, String, Text
from .base import Base, TimestampMixin, new_uuid


class MessageModel(Base, TimestampMixin):
    __tablename__ = "messages"

    id                  = Column(String(36),  primary_key=True, default=new_uuid)
    lead_id             = Column(String(36),  nullable=False, index=True)
    deal_id             = Column(String(36),  nullable=True)
    channel             = Column(String(20),  nullable=False, index=True)   # whatsapp|email|sms
    direction           = Column(String(10),  nullable=False, index=True)   # inbound|outbound
    subject             = Column(String(300), nullable=True)                # email only
    body                = Column(Text,        nullable=True)
    provider_message_id = Column(String(120), nullable=True, index=True)   # Meta/provider ID
    status              = Column(String(20),  nullable=False, default="sent", index=True)
    sent_at_il          = Column(String(40),  nullable=True)
    delivered_at_il     = Column(String(40),  nullable=True)
    read_at_il          = Column(String(40),  nullable=True)
    raw_payload         = Column(Text,        nullable=True)   # JSON webhook payload (inbound)

    def to_dict(self) -> dict:
        return {
            "id":                  self.id,
            "lead_id":             self.lead_id,
            "deal_id":             self.deal_id,
            "channel":             self.channel,
            "direction":           self.direction,
            "subject":             self.subject,
            "body":                self.body,
            "provider_message_id": self.provider_message_id,
            "status":              self.status,
            "sent_at_il":          self.sent_at_il,
            "delivered_at_il":     self.delivered_at_il,
            "read_at_il":          self.read_at_il,
            "created_at":          str(self.created_at) if self.created_at else None,
        }
