"""
events/handlers/lead_acquisition_handlers.py
Phase 12: Lead Acquisition OS

Handlers for new lead acquisition events:
  on_lead_discovered         — LEAD_DISCOVERED
  on_inbound_lead_received   — INBOUND_LEAD_RECEIVED
  on_lead_outreach_sent      — LEAD_OUTREACH_SENT
  on_lead_followup_proposed  — LEAD_FOLLOWUP_PROPOSED
  on_website_analysis_requested — WEBSITE_ANALYSIS_REQUESTED
"""

import logging
from typing import Any

log = logging.getLogger(__name__)


def on_lead_discovered(event: dict[str, Any]) -> None:
    """
    Fired when lead_acquisition_engine discovers a new candidate from a web signal.
    Hook: update discovery session, trigger scoring refresh, notify briefing.
    """
    payload    = event.get("payload") or {}
    lead_id    = payload.get("lead_id")
    session_id = payload.get("session_id")
    score      = payload.get("score", 0)
    source     = payload.get("source_type")

    log.info(
        f"[LeadAcquisition] LEAD_DISCOVERED lead={lead_id} "
        f"session={session_id} score={score} source={source}"
    )

    # Hook: auto-flag high-score discovered leads for review
    if score and int(score) >= 70:
        try:
            from services.storage.db import get_session
            from services.storage.repositories.lead_repo import LeadRepository
            with get_session() as session:
                repo = LeadRepository(session)
                lead = repo.get_by_id(lead_id) if lead_id else None
                if lead:
                    lead.status = "ליד חם — נגלה"
                    lead.last_activity_at = _now_iso()
        except Exception as e:
            log.warning(f"[on_lead_discovered] status update failed: {e}")


def on_inbound_lead_received(event: dict[str, Any]) -> None:
    """
    Fired when an inbound lead arrives (Telegram/form/WhatsApp).
    Hook: set priority status, trigger draft approval flow.
    """
    payload = event.get("payload") or {}
    lead_id = payload.get("lead_id")
    score   = payload.get("score", 0)
    source  = payload.get("source", "inbound")

    log.info(f"[LeadAcquisition] INBOUND_LEAD_RECEIVED lead={lead_id} score={score} source={source}")

    try:
        from services.storage.db import get_session
        from services.storage.repositories.lead_repo import LeadRepository
        with get_session() as session:
            repo = LeadRepository(session)
            lead = repo.get_by_id(lead_id) if lead_id else None
            if lead:
                lead.status = "ליד נכנס — ממתין לתגובה"
                lead.last_activity_at = _now_iso()
                # If there's a draft ready, mark it for approval
                if getattr(lead, "outreach_draft", None):
                    _create_approval_for_inbound(lead_id, lead)
    except Exception as e:
        log.warning(f"[on_inbound_lead_received] update failed: {e}")


def on_lead_outreach_sent(event: dict[str, Any]) -> None:
    """
    Fired after an approved outreach message is sent to a lead.
    Hook: update lead status, increment attempts, schedule follow-up.
    """
    payload = event.get("payload") or {}
    lead_id = payload.get("lead_id")
    channel = payload.get("channel")
    action  = payload.get("action")

    log.info(f"[LeadAcquisition] LEAD_OUTREACH_SENT lead={lead_id} channel={channel} action={action}")

    try:
        from services.storage.db import get_session
        from services.storage.repositories.lead_repo import LeadRepository
        import datetime
        with get_session() as session:
            repo = LeadRepository(session)
            lead = repo.get_by_id(lead_id) if lead_id else None
            if lead:
                lead.attempts        = (lead.attempts or 0) + 1
                lead.last_contact    = _now_iso()
                lead.last_activity_at = _now_iso()
                lead.status          = "נשלחה פנייה"
                # Schedule follow-up: 3 days out
                due = (datetime.datetime.utcnow() + datetime.timedelta(days=3)).date().isoformat()
                lead.next_action     = "follow_up"
                lead.next_action_due = due
    except Exception as e:
        log.warning(f"[on_lead_outreach_sent] update failed: {e}")


def on_lead_followup_proposed(event: dict[str, Any]) -> None:
    """
    Fired when a follow-up action is proposed for a lead.
    Hook: set meeting_suggested if action is meeting_request.
    """
    payload = event.get("payload") or {}
    lead_id = payload.get("lead_id")
    action  = payload.get("action")

    log.info(f"[LeadAcquisition] LEAD_FOLLOWUP_PROPOSED lead={lead_id} action={action}")

    if action == "meeting_request":
        try:
            from services.storage.db import get_session
            from services.storage.repositories.lead_repo import LeadRepository
            with get_session() as session:
                repo = LeadRepository(session)
                lead = repo.get_by_id(lead_id) if lead_id else None
                if lead and hasattr(lead, "meeting_suggested"):
                    lead.meeting_suggested = "true"
        except Exception as e:
            log.warning(f"[on_lead_followup_proposed] update failed: {e}")


def on_website_analysis_requested(event: dict[str, Any]) -> None:
    """
    Fired when website_analysis route runs.
    Hook: log for audit trail (lightweight).
    """
    payload = event.get("payload") or {}
    url     = payload.get("url")
    score   = payload.get("audit_score")
    log.info(f"[LeadAcquisition] WEBSITE_ANALYSIS_REQUESTED url={url} score={score}")


# ── Private helpers ────────────────────────────────────────────────────────────

def _now_iso() -> str:
    import datetime
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _create_approval_for_inbound(lead_id: str, lead: Any) -> None:
    """Create an approval record for an inbound lead draft."""
    try:
        from services.storage.db import get_session
        from services.storage.models.approval import ApprovalModel
        with get_session() as session:
            approval = ApprovalModel(
                action="inbound_response",
                details={
                    "lead_id":   lead_id,
                    "lead_name": getattr(lead, "name", ""),
                    "draft":     getattr(lead, "outreach_draft", ""),
                    "channel":   getattr(lead, "source_type", ""),
                },
                risk_level=2,
                status="pending",
                requested_by="lead_acquisition_engine",
            )
            session.add(approval)
    except Exception as e:
        log.warning(f"[_create_approval_for_inbound] failed: {e}")
