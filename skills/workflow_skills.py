"""
skills/workflow_skills.py — Workflow Skills
Phase 12: Lead Acquisition OS

Build work queue, mark approval, push to CRM, update status.
Stateless where possible — DB access via repositories passed as args.

CONTRACT:
  build_work_queue(leads: list[dict], context: dict) -> WorkQueue
  mark_approval_required(item: dict, reason: str) -> dict
  push_to_crm(lead: dict, session) -> str              # returns lead_id
  update_lead_status(lead_id: str, status: str, note: str, session) -> bool
  queue_next_action(lead_id: str, action: str, due: str, session) -> bool
"""

from __future__ import annotations
import datetime
from dataclasses import dataclass, field
from typing import Any


# ── Data contracts ────────────────────────────────────────────────────────────

@dataclass
class WorkItem:
    lead_id:           str
    lead_name:         str
    action:            str            # dm | follow_up | meeting_request | comment_reply | wait
    channel:           str
    draft:             str            # drafted message body
    priority:          str            # high | medium | low
    approval_required: bool
    approval_status:   str = "pending"  # pending | approved | denied | not_required
    notes:             list[str] = field(default_factory=list)
    due_at:            str = ""       # ISO-8601


@dataclass
class WorkQueue:
    items:         list[WorkItem]
    total:         int = 0
    needs_approval: int = 0
    ready:         int = 0
    waiting:       int = 0

    def __post_init__(self):
        self.total          = len(self.items)
        self.needs_approval = sum(1 for i in self.items if i.approval_required and i.approval_status == "pending")
        self.ready          = sum(1 for i in self.items if i.approval_status == "approved")
        self.waiting        = sum(1 for i in self.items if i.action == "wait")


# ── Work queue ────────────────────────────────────────────────────────────────

def build_work_queue(
    leads: list[dict[str, Any]],
    context: dict[str, Any] | None = None,
) -> WorkQueue:
    """
    Build a prioritized work queue from scored leads.
    Each lead must have: id, name, outreach_action, outreach_draft,
    priority, channel, is_inbound, score.
    """
    ctx = context or {}
    items: list[WorkItem] = []
    for lead in leads:
        action  = lead.get("outreach_action") or "wait"
        draft   = lead.get("outreach_draft")  or ""
        channel = lead.get("channel")         or ""
        priority = lead.get("priority")       or "low"
        requires_approval = action != "wait"
        due = _default_due(priority)

        items.append(WorkItem(
            lead_id=lead.get("id") or "",
            lead_name=lead.get("name") or "לא ידוע",
            action=action,
            channel=channel,
            draft=draft,
            priority=priority,
            approval_required=requires_approval,
            approval_status="not_required" if not requires_approval else "pending",
            notes=lead.get("fit_reasons") or [],
            due_at=due,
        ))

    # Sort: inbound first, then by priority score
    _priority_order = {"high": 3, "medium": 2, "low": 1}
    items.sort(
        key=lambda i: (_is_inbound(i, leads), _priority_order.get(i.priority, 0)),
        reverse=True,
    )
    return WorkQueue(items=items)


def mark_approval_required(item: dict[str, Any], reason: str = "") -> dict[str, Any]:
    """Return a copy of the item marked as requiring approval."""
    return {
        **item,
        "approval_required": True,
        "approval_status":   "pending",
        "approval_reason":   reason or "פעולה רגישה — נדרש אישור לפני ביצוע",
    }


# ── CRM push ──────────────────────────────────────────────────────────────────

def push_to_crm(lead: dict[str, Any], session: Any) -> str:
    """
    Persist a discovered/inbound lead to DB via LeadRepository.
    Returns the new or existing lead_id.
    """
    from services.storage.repositories.lead_repo import LeadRepository

    repo = LeadRepository(session)
    # Check for existing by phone/email
    existing = None
    if lead.get("phone"):
        existing = repo.find_by_phone(lead["phone"])
    if not existing and lead.get("email"):
        existing = repo.find_by_email(lead["email"])

    if existing:
        return existing.id

    from services.storage.models.lead import LeadModel
    new_lead = LeadModel(
        name=lead.get("name") or "ליד חדש",
        phone=lead.get("phone") or "",
        email=lead.get("email") or "",
        city=lead.get("city") or "",
        company=lead.get("company") or "",
        source=lead.get("source_type") or "acquisition",
        sector="aluminum",
        score=lead.get("score") or 0,
        status="חדש",
        notes=lead.get("notes") or "",
        next_action=lead.get("outreach_draft") or "",
    )
    # Extended columns (added via migration)
    for col in ("source_type", "source_url", "segment", "outreach_action",
                "outreach_draft", "is_inbound", "discovery_session_id",
                "meeting_suggested", "geo_fit_score"):
        if hasattr(new_lead, col) and col in lead:
            setattr(new_lead, col, lead[col])

    session.add(new_lead)
    session.flush()
    return new_lead.id


def update_lead_status(
    lead_id: str,
    status: str,
    note: str = "",
    session: Any = None,
) -> bool:
    """Update lead status and append a history note."""
    if not session:
        return False
    from services.storage.repositories.lead_repo import LeadRepository
    repo = LeadRepository(session)
    lead = repo.get_by_id(lead_id)
    if not lead:
        return False
    lead.status = status
    if note:
        lead.notes = f"{lead.notes or ''}\n[{_now_iso()}] {note}".strip()
    lead.last_activity_at = _now_iso()
    return True


def queue_next_action(
    lead_id: str,
    action: str,
    due: str = "",
    session: Any = None,
) -> bool:
    """Set the next_action and next_action_due on a lead."""
    if not session:
        return False
    from services.storage.repositories.lead_repo import LeadRepository
    repo = LeadRepository(session)
    lead = repo.get_by_id(lead_id)
    if not lead:
        return False
    lead.next_action     = action
    lead.next_action_due = due or _default_due("medium")
    return True


# ── Private helpers ────────────────────────────────────────────────────────────

def _now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _default_due(priority: str) -> str:
    delta = {"high": 1, "medium": 3, "low": 7}.get(priority, 3)
    due = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=delta)
    return due.date().isoformat()


def _is_inbound(item: WorkItem, leads: list[dict]) -> int:
    for lead in leads:
        if lead.get("id") == item.lead_id and lead.get("is_inbound"):
            return 1
    return 0
