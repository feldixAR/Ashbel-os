"""
services/growth/followup_engine.py — Batch 9: Follow-up Engine.

process_pending_followups():
  1. Query OutreachModel WHERE lifecycle_status = 'followup_due'
  2. For each record:
     a. Generate a "gentle reminder" asset via AssetFactory
     b. Persist a new OutreachModel row (status=ready, linked via parent_record_id)
     c. Update parent record lifecycle_status → 'followup_sent'
  3. Return a summary list of FollowupResult

Human-in-the-loop:
  Follow-up records are created with status='ready'.
  Actual dispatch (Telegram notification) is triggered separately via
  dispatch_record() — either manually or by the scheduler.
  This preserves the human-in-the-loop constraint.
"""

from __future__ import annotations

import datetime
import logging
import uuid
from dataclasses import dataclass, field
from typing import List

import pytz as _pytz

log = logging.getLogger(__name__)
_IL_TZ = _pytz.timezone("Asia/Jerusalem")

# ── Result contract ────────────────────────────────────────────────────────────

@dataclass
class FollowupResult:
    parent_record_id:  str
    child_record_id:   str
    goal_id:           str
    channel:           str
    asset_type:        str
    success:           bool
    error:             str = ""

    def to_dict(self) -> dict:
        return {
            "parent_record_id": self.parent_record_id,
            "child_record_id":  self.child_record_id,
            "goal_id":          self.goal_id,
            "channel":          self.channel,
            "asset_type":       self.asset_type,
            "success":          self.success,
            "error":            self.error,
        }


# ── Main entry point ───────────────────────────────────────────────────────────

def process_pending_followups(limit: int = 20) -> List[FollowupResult]:
    """
    Find all outreach records that are overdue for a follow-up and
    generate reminder assets for each.

    Returns a list of FollowupResult — one per processed record.
    """
    from services.storage.db import get_session
    from services.storage.models.outreach import OutreachModel

    with get_session() as session:
        due_records = (
            session.query(OutreachModel)
            .filter_by(lifecycle_status="followup_due")
            .order_by(OutreachModel.next_action_at)
            .limit(limit)
            .all()
        )
        # Snapshot to avoid lazy-load issues after session closes
        snapshots = [_snapshot(r) for r in due_records]

    log.info(f"[FollowupEngine] {len(snapshots)} records due for follow-up")

    results: List[FollowupResult] = []
    for snap in snapshots:
        result = _process_one(snap)
        results.append(result)

    return results


# ── Per-record processor ───────────────────────────────────────────────────────

def _process_one(snap: dict) -> FollowupResult:
    """Generate a follow-up asset for one overdue record."""
    parent_id = snap["id"]
    goal_id   = snap["goal_id"]
    opp_id    = snap["opp_id"] or ""
    channel   = snap["channel"]
    audience  = snap.get("audience") or "general"
    orig_name = snap["contact_name"] or ""

    try:
        # ── a. Generate gentle reminder asset ─────────────────────────────────
        child_id  = str(uuid.uuid4())
        now_il    = datetime.datetime.now(_IL_TZ).isoformat()
        reminder  = _build_reminder_asset(orig_name, channel, audience)

        # ── b. Persist follow-up OutreachModel row ────────────────────────────
        from services.storage.db import get_session
        from services.storage.models.outreach import OutreachModel
        from services.growth.policy import compute_next_action_at

        with get_session() as session:
            session.add(OutreachModel(
                id=child_id,
                goal_id=goal_id,
                opp_id=opp_id,
                parent_record_id=parent_id,
                contact_name=f"[followup] {orig_name}",
                contact_phone=snap.get("contact_phone") or "",
                channel=channel,
                message_body=reminder,
                status="ready",
                lifecycle_status="sent",          # will transition after dispatch
                next_action_at=compute_next_action_at(channel, now_il),
                notes=f"Follow-up for parent={parent_id}",
            ))

        # ── c. Update parent → followup_sent ─────────────────────────────────
        _set_lifecycle(parent_id, "followup_sent")

        log.info(
            f"[FollowupEngine] generated follow-up child={child_id} "
            f"parent={parent_id} channel={channel}"
        )
        return FollowupResult(
            parent_record_id=parent_id,
            child_record_id=child_id,
            goal_id=goal_id,
            channel=channel,
            asset_type="followup_whatsapp",
            success=True,
        )

    except Exception as e:
        log.error(
            f"[FollowupEngine] failed parent={parent_id}: {e}", exc_info=True
        )
        return FollowupResult(
            parent_record_id=parent_id,
            child_record_id="",
            goal_id=goal_id,
            channel=channel,
            asset_type="",
            success=False,
            error=str(e),
        )


# ── Asset builder ──────────────────────────────────────────────────────────────

_AUDIENCE_LABELS: dict[str, str] = {
    "contractors":        "קבלנים",
    "architects":         "אדריכלים",
    "interior_designers": "מעצבי פנים",
    "general":            "לקוח יקר",
}

def _build_reminder_asset(orig_name: str, channel: str, audience: str) -> str:
    """Generate a short, friendly follow-up reminder message."""
    label = _AUDIENCE_LABELS.get(audience, "לקוח יקר")
    # Strip asset_type prefix if present
    display = orig_name
    if "] " in orig_name:
        display = orig_name.split("] ", 1)[-1]

    if channel in ("whatsapp", "email"):
        return (
            f"שלום 😊\n\n"
            f"פנינו אליכם לפני מספר ימים בנושא פתרון אלומיניום ל{label}.\n\n"
            f"רצינו לבדוק אם יש לכם שאלות או אם תרצו לקבל הצעת מחיר מפורטת.\n\n"
            f"אנחנו כאן לכל שאלה 🙏\n\n"
            f"צוות אשבל אלומיניום"
        )
    return f"[Reminder] Follow-up for {display} — {audience}"


# ── DB helpers ─────────────────────────────────────────────────────────────────

def _snapshot(record) -> dict:
    """Extract fields from OutreachModel before session closes."""
    return {
        "id":            record.id,
        "goal_id":       record.goal_id,
        "opp_id":        record.opp_id,
        "contact_name":  record.contact_name,
        "contact_phone": record.contact_phone,
        "channel":       record.channel,
        "audience":      getattr(record, "audience", "general"),
        "next_action_at": getattr(record, "next_action_at", None),
    }


def promote_overdue_records() -> int:
    """
    Sweep OutreachModel WHERE lifecycle_status='awaiting_response'
    AND next_action_at <= now → set lifecycle_status='followup_due'.

    This bridges the gap between 'awaiting_response' (set after send) and
    'followup_due' (consumed by process_pending_followups). Must run before
    process_pending_followups() for the follow-up cycle to work end-to-end.

    Returns count of records promoted.
    """
    from services.storage.db import get_session
    from services.storage.models.outreach import OutreachModel
    from services.growth.policy import is_followup_overdue

    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    promoted = 0
    try:
        with get_session() as session:
            candidates = (
                session.query(OutreachModel)
                .filter_by(lifecycle_status="awaiting_response")
                .filter(OutreachModel.next_action_at.isnot(None))
                .all()
            )
            for rec in candidates:
                if is_followup_overdue(rec.next_action_at):
                    rec.lifecycle_status = "followup_due"
                    promoted += 1
        log.info(f"[FollowupEngine] promoted {promoted} records → followup_due")
    except Exception as e:
        log.error(f"[FollowupEngine] promote_overdue_records failed: {e}", exc_info=True)
    return promoted


def _set_lifecycle(record_id: str, lifecycle_status: str) -> None:
    try:
        from services.storage.db import get_session
        from services.storage.models.outreach import OutreachModel

        with get_session() as session:
            record = session.query(OutreachModel).filter_by(id=record_id).first()
            if record:
                record.lifecycle_status = lifecycle_status
    except Exception as e:
        log.error(
            f"[FollowupEngine] _set_lifecycle failed id={record_id}: {e}",
            exc_info=True,
        )
