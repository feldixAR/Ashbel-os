"""
channel_base.py — Base classes for all channel services.

ChannelStatus values:
  active       — fully automated, credentials present
  readiness    — draft/preview/manual-send only; execution needs credentials
  blocked      — not available (missing account, policy block)
  manual_only  — always manual; no automation planned
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class ChannelStatus(str, Enum):
    ACTIVE      = "active"
    READINESS   = "readiness"
    BLOCKED     = "blocked"
    MANUAL_ONLY = "manual_only"


@dataclass
class ChannelResult:
    channel:       str
    status:        ChannelStatus
    draft:         str = ""
    subject:       str = ""
    preview_html:  str = ""
    manual_instructions: str = ""
    deep_link:     str = ""
    copy_text:     str = ""
    needs_approval: bool = True
    meta:          dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "channel":             self.channel,
            "status":              self.status.value if isinstance(self.status, ChannelStatus) else self.status,
            "draft":               self.draft,
            "subject":             self.subject,
            "preview_html":        self.preview_html,
            "manual_instructions": self.manual_instructions,
            "deep_link":           self.deep_link,
            "copy_text":           self.copy_text,
            "needs_approval":      self.needs_approval,
            "meta":                self.meta,
        }
