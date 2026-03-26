"""
services/outreach/execution_record.py — Batch 7: Outreach & Execution Engine.

Service layer for tracking outreach executions:
  - log_execution()   → persist a new OutreachModel record
  - mark_sent()       → update status to 'sent'
  - mark_replied()    → update status to 'replied'
  - list_due()        → return records where next_followup <= now
"""
from __future__ import annotations

import datetime
import logging
from typing import List

log = logging.getLogger(__name__)


# ── Execution logger ────────────────────────────────────────────────────────────

def log_execution(
    goal_id:       str,
    opp_id:        str,
    contact_name:  str,
    contact_phone: str,
    channel:       str,
    message_body:  str,
) -> dict:
    """
    Persist a new outreach execution record and return its dict representation.
    Status is set to 'pending' by default.
    """
    from services.storage.repositories.outreach_repo import OutreachRepository

    record = OutreachRepository().create(
        goal_id=goal_id,
        opp_id=opp_id,
        contact_name=contact_name,
        contact_phone=contact_phone,
        channel=channel,
        message_body=message_body,
    )
    log.info(
        f"[ExecutionRecord] Logged outreach id={record.id} "
        f"contact={contact_name} channel={channel} goal={goal_id}"
    )
    return record.to_dict()


def mark_sent(record_id: str) -> bool:
    """
    Update outreach record status → 'sent' and set sent_at to current UTC time.
    Returns True on success, False if record not found.
    """
    from services.storage.db import get_session
    from services.storage.models.outreach import OutreachModel

    with get_session() as session:
        record = session.query(OutreachModel).filter_by(id=record_id).first()
        if not record:
            log.warning(f"[ExecutionRecord] mark_sent: record {record_id} not found")
            return False
        record.status  = "sent"
        record.sent_at = datetime.datetime.utcnow().isoformat()

    log.info(f"[ExecutionRecord] Marked sent: id={record_id}")
    return True


def mark_replied(record_id: str, notes: str = "") -> bool:
    """
    Update outreach record status → 'replied' and record reply timestamp.
    Returns True on success, False if record not found.
    """
    from services.storage.db import get_session
    from services.storage.models.outreach import OutreachModel

    with get_session() as session:
        record = session.query(OutreachModel).filter_by(id=record_id).first()
        if not record:
            log.warning(f"[ExecutionRecord] mark_replied: record {record_id} not found")
            return False
        record.status     = "replied"
        record.replied_at = datetime.datetime.utcnow().isoformat()
        if notes:
            record.notes = notes

    log.info(f"[ExecutionRecord] Marked replied: id={record_id}")
    return True


def list_due(limit: int = 20) -> List[dict]:
    """
    Return outreach records where next_followup <= now and status in pending/sent.
    Useful for follow-up reminders.
    """
    from services.storage.repositories.outreach_repo import OutreachRepository

    records = OutreachRepository().list_due_followup()
    due = records[:limit]
    log.info(f"[ExecutionRecord] {len(due)} records due for follow-up")
    return [r.to_dict() for r in due]
