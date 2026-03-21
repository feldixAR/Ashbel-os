"""
Lead event handlers.

Triggered by: LEAD_CREATED, LEAD_SCORED, LEAD_RESPONDED, LEAD_STATUS_CHANGED

Responsibilities:
  - Log lead lifecycle transitions
  - Trigger follow-up scheduling when a lead is created
  - Update memory/learning on response events
  - Route hot leads to closing workflow
"""

import logging
from memory.memory_store import MemoryStore

log = logging.getLogger(__name__)


def on_lead_created(event_type: str, payload: dict, meta: dict) -> None:
    """
    A new lead entered the system.
    Schedules initial scoring and outreach check.
    """
    lead_id   = payload.get("lead_id")
    lead_name = payload.get("name", "unknown")
    source    = payload.get("source", "unknown")

    log.info(f"[LeadHandler] new lead: {lead_name} (id={lead_id}, source={source})")

    # Track total leads created per source for lead quality learning
    key = f"leads_created_from_{source}"
    current = MemoryStore.read("leads", key, 0)
    MemoryStore.write("leads", key, current + 1)


def on_lead_scored(event_type: str, payload: dict, meta: dict) -> None:
    """
    A lead received a new score.
    If score >= 70, marks as hot and logs for routing to closing workflow.
    """
    lead_id = payload.get("lead_id")
    score   = payload.get("score", 0)
    name    = payload.get("name", "unknown")

    log.info(f"[LeadHandler] scored: {name} (id={lead_id}) → score={score}")

    if score >= 70:
        log.info(f"[LeadHandler] HOT LEAD detected: {name} score={score}")
        # Record hot leads for reporting
        hot_leads = MemoryStore.read("leads", "hot_lead_ids", [])
        if lead_id and lead_id not in hot_leads:
            hot_leads.append(lead_id)
            MemoryStore.write("leads", "hot_lead_ids", hot_leads)


def on_lead_responded(event_type: str, payload: dict, meta: dict) -> None:
    """
    A lead replied to an outreach message.
    Classifies the response type and updates learning memory.
    """
    lead_id       = payload.get("lead_id")
    response_type = payload.get("response_type", "unknown")
    message_type  = payload.get("message_type", "unknown")

    log.info(
        f"[LeadHandler] response received: lead={lead_id} "
        f"type={response_type} message_type={message_type}"
    )

    # Track response rates per message type for learning
    key = f"responses_for_{message_type}"
    stats = MemoryStore.read("messaging", key, {"total": 0, "positive": 0})
    stats["total"] += 1
    if response_type in ("חם", "מתעניין", "בקשת_מידע"):
        stats["positive"] += 1
    MemoryStore.write("messaging", key, stats)


def on_lead_status_changed(event_type: str, payload: dict, meta: dict) -> None:
    """
    A lead's status changed.
    Tracks conversion funnel metrics in memory.
    """
    lead_id    = payload.get("lead_id")
    old_status = payload.get("old_status", "")
    new_status = payload.get("new_status", "")

    log.info(
        f"[LeadHandler] status change: lead={lead_id} "
        f"{old_status} → {new_status}"
    )

    # Track funnel step counts
    if new_status:
        key = f"count_status_{new_status}"
        current = MemoryStore.read("leads", key, 0)
        MemoryStore.write("leads", key, current + 1)

    if new_status == "סגור_זכה":
        won = MemoryStore.read("leads", "total_won", 0)
        MemoryStore.write("leads", "total_won", won + 1)
        log.info(f"[LeadHandler] CONVERSION: lead={lead_id} → WON")
