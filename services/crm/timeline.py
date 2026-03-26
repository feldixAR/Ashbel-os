"""
services/crm/timeline.py — Unified Timeline per Lead.

Aggregates all touchpoints into a single chronological feed:
  - WhatsApp / Email messages     (MessageModel)
  - Calls, meetings, notes        (ActivityModel)
  - Calendar events               (CalendarEventModel)
  - Deal stage transitions        (StageHistoryModel)
  - CRM history entries           (LeadHistoryModel)

build_timeline(lead_id, limit=50) → List[TimelineEvent] sorted newest-first.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import List, Optional

log = logging.getLogger(__name__)


@dataclass
class TimelineEvent:
    event_id:   str
    event_type: str       # message | activity | calendar | stage_change | crm_note
    channel:    str       # whatsapp | email | call | meeting | system | ...
    direction:  str       # inbound | outbound | internal
    summary:    str       # one-line human-readable description
    body:       str       # full content
    occurred_at: str      # ISO-8601 IL tz (best available)
    metadata:   dict

    def to_dict(self) -> dict:
        return {
            "event_id":   self.event_id,
            "event_type": self.event_type,
            "channel":    self.channel,
            "direction":  self.direction,
            "summary":    self.summary,
            "body":       self.body,
            "occurred_at": self.occurred_at,
            "metadata":   self.metadata,
        }


def build_timeline(lead_id: str, limit: int = 50) -> List[TimelineEvent]:
    """
    Return all touchpoints for a lead, sorted newest-first.
    Each source is queried independently; failures are logged and skipped.
    """
    events: List[TimelineEvent] = []

    events.extend(_messages(lead_id))
    events.extend(_activities(lead_id))
    events.extend(_calendar(lead_id))
    events.extend(_stage_history(lead_id))
    events.extend(_crm_history(lead_id))

    events.sort(key=lambda e: e.occurred_at or "", reverse=True)
    return events[:limit]


# ── Source extractors ──────────────────────────────────────────────────────────

def _messages(lead_id: str) -> List[TimelineEvent]:
    try:
        from services.storage.db import get_session
        from services.storage.models.message import MessageModel
        with get_session() as s:
            rows = (s.query(MessageModel)
                    .filter_by(lead_id=lead_id)
                    .order_by(MessageModel.created_at.desc())
                    .limit(30).all())
        result = []
        for r in rows:
            ts = r.sent_at_il or str(r.created_at or "")
            result.append(TimelineEvent(
                event_id=r.id,
                event_type="message",
                channel=r.channel,
                direction=r.direction,
                summary=f"[{r.channel}/{r.direction}] {(r.body or '')[:80]}",
                body=r.body or "",
                occurred_at=ts,
                metadata={"status": r.status, "message_id": r.provider_message_id},
            ))
        return result
    except Exception as e:
        log.warning(f"[Timeline] messages failed lead={lead_id}: {e}")
        return []


def _activities(lead_id: str) -> List[TimelineEvent]:
    try:
        from services.storage.db import get_session
        from services.storage.models.activity import ActivityModel
        with get_session() as s:
            rows = (s.query(ActivityModel)
                    .filter_by(lead_id=lead_id)
                    .order_by(ActivityModel.created_at.desc())
                    .limit(30).all())
        result = []
        for r in rows:
            ts = r.performed_at_il or str(r.created_at or "")
            summary = f"[{r.activity_type}] {r.subject or r.outcome or '—'}"
            result.append(TimelineEvent(
                event_id=r.id,
                event_type="activity",
                channel=r.activity_type,
                direction=r.direction,
                summary=summary,
                body=r.notes or "",
                occurred_at=ts,
                metadata={"outcome": r.outcome, "duration_sec": r.duration_sec,
                          "performed_by": r.performed_by},
            ))
        return result
    except Exception as e:
        log.warning(f"[Timeline] activities failed lead={lead_id}: {e}")
        return []


def _calendar(lead_id: str) -> List[TimelineEvent]:
    try:
        from services.storage.db import get_session
        from services.storage.models.calendar_event import CalendarEventModel
        with get_session() as s:
            rows = (s.query(CalendarEventModel)
                    .filter_by(lead_id=lead_id)
                    .order_by(CalendarEventModel.created_at.desc())
                    .limit(20).all())
        result = []
        for r in rows:
            result.append(TimelineEvent(
                event_id=r.id,
                event_type="calendar",
                channel=r.event_type,
                direction="internal",
                summary=f"[{r.event_type}] {r.title} — {r.status}",
                body=r.notes or "",
                occurred_at=r.starts_at_il or str(r.created_at or ""),
                metadata={"status": r.status, "location": r.location},
            ))
        return result
    except Exception as e:
        log.warning(f"[Timeline] calendar failed lead={lead_id}: {e}")
        return []


def _stage_history(lead_id: str) -> List[TimelineEvent]:
    try:
        from services.storage.db import get_session
        from services.storage.models.stage_history import StageHistoryModel
        with get_session() as s:
            rows = (s.query(StageHistoryModel)
                    .filter_by(lead_id=lead_id)
                    .order_by(StageHistoryModel.created_at.desc())
                    .limit(20).all())
        result = []
        for r in rows:
            result.append(TimelineEvent(
                event_id=r.id,
                event_type="stage_change",
                channel="system",
                direction="internal",
                summary=f"שלב שונה: {r.from_stage} → {r.to_stage}",
                body=r.reason or "",
                occurred_at=r.changed_at_il or str(r.created_at or ""),
                metadata={"from": r.from_stage, "to": r.to_stage,
                          "changed_by": r.changed_by, "deal_id": r.deal_id},
            ))
        return result
    except Exception as e:
        log.warning(f"[Timeline] stage_history failed lead={lead_id}: {e}")
        return []


def _crm_history(lead_id: str) -> List[TimelineEvent]:
    try:
        from services.storage.db import get_session
        from services.storage.models.lead import LeadHistoryModel
        with get_session() as s:
            rows = (s.query(LeadHistoryModel)
                    .filter_by(lead_id=lead_id)
                    .order_by(LeadHistoryModel.created_at.desc())
                    .limit(20).all())
        result = []
        for r in rows:
            result.append(TimelineEvent(
                event_id=r.id,
                event_type="crm_note",
                channel="system",
                direction="internal",
                summary=f"[{r.action}] {(r.note or '')[:80]}",
                body=r.note or "",
                occurred_at=str(r.created_at or ""),
                metadata={"action": r.action, "agent_id": r.agent_id},
            ))
        return result
    except Exception as e:
        log.warning(f"[Timeline] crm_history failed lead={lead_id}: {e}")
        return []
