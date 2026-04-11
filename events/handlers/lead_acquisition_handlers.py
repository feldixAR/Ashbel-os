"""
events/handlers/lead_acquisition_handlers.py
Phase 12: Lead Acquisition OS

Handlers for new lead acquisition events.
"""

import logging
from typing import Any

log = logging.getLogger(__name__)


def on_lead_discovered(event: dict[str, Any]) -> None:
    """Auto-flag high-score discovered leads + push Telegram alert for hot leads."""
    payload    = event.get("payload") or {}
    lead_id    = payload.get("lead_id")
    session_id = payload.get("session_id")
    score      = payload.get("score", 0)
    source     = payload.get("source_type")

    log.info(f"[LeadAcquisition] LEAD_DISCOVERED lead={lead_id} session={session_id} score={score} source={source}")

    if lead_id and score and int(score) >= 70:
        try:
            from services.storage.repositories.lead_repo import LeadRepository
            repo = LeadRepository()
            repo.update_status(lead_id, "ליד חם — נגלה")

            # Telegram alert for hot leads (non-blocking)
            lead = repo.get_by_id(lead_id)
            if lead:
                _telegram_hot_lead_alert(lead, int(score), source or "")
        except Exception as e:
            log.warning(f"[on_lead_discovered] status update failed: {e}")


def on_inbound_lead_received(event: dict[str, Any]) -> None:
    """Set priority status for inbound lead, trigger approval draft."""
    payload = event.get("payload") or {}
    lead_id = payload.get("lead_id")
    score   = payload.get("score", 0)
    source  = payload.get("source", "inbound")

    log.info(f"[LeadAcquisition] INBOUND_LEAD_RECEIVED lead={lead_id} score={score} source={source}")

    if lead_id:
        try:
            from services.storage.repositories.lead_repo import LeadRepository
            repo = LeadRepository()
            repo.update_status(lead_id, "ליד נכנס — ממתין לתגובה")
            # If draft exists, create approval record
            lead = repo.get_by_id(lead_id)
            if lead and getattr(lead, "outreach_draft", None):
                _create_approval_for_inbound(lead_id, lead)
        except Exception as e:
            log.warning(f"[on_inbound_lead_received] update failed: {e}")


def on_lead_outreach_sent(event: dict[str, Any]) -> None:
    """Update lead after approved outreach is sent: status, attempts, follow-up."""
    payload = event.get("payload") or {}
    lead_id = payload.get("lead_id")
    channel = payload.get("channel")
    action  = payload.get("action")

    log.info(f"[LeadAcquisition] LEAD_OUTREACH_SENT lead={lead_id} channel={channel} action={action}")

    if lead_id:
        try:
            import datetime
            from services.storage.db import get_session
            from services.storage.models.lead import LeadModel
            due = (datetime.datetime.utcnow() + datetime.timedelta(days=3)).date().isoformat()
            with get_session() as s:
                lead = s.get(LeadModel, lead_id)
                if lead:
                    lead.attempts         = (lead.attempts or 0) + 1
                    lead.last_contact     = _now_iso()
                    lead.last_activity_at = _now_iso()
                    lead.status           = "נשלחה פנייה"
                    lead.next_action      = "follow_up"
                    lead.next_action_due  = due
        except Exception as e:
            log.warning(f"[on_lead_outreach_sent] update failed: {e}")


def on_lead_followup_proposed(event: dict[str, Any]) -> None:
    """Mark meeting_suggested if action is meeting_request."""
    payload = event.get("payload") or {}
    lead_id = payload.get("lead_id")
    action  = payload.get("action")

    log.info(f"[LeadAcquisition] LEAD_FOLLOWUP_PROPOSED lead={lead_id} action={action}")

    if lead_id and action == "meeting_request":
        try:
            from services.storage.db import get_session
            from services.storage.models.lead import LeadModel
            with get_session() as s:
                lead = s.get(LeadModel, lead_id)
                if lead and hasattr(lead, "meeting_suggested"):
                    lead.meeting_suggested = "true"
        except Exception as e:
            log.warning(f"[on_lead_followup_proposed] update failed: {e}")


def on_website_analysis_requested(event: dict[str, Any]) -> None:
    """Log website analysis request for audit trail."""
    payload = event.get("payload") or {}
    log.info(f"[LeadAcquisition] WEBSITE_ANALYSIS_REQUESTED url={payload.get('url')} score={payload.get('audit_score')}")


# ── Private helpers ────────────────────────────────────────────────────────────

def _now_iso() -> str:
    import datetime
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _create_approval_for_inbound(lead_id: str, lead: Any) -> None:
    approval_id = None
    try:
        from services.storage.db import get_session
        from services.storage.models.approval import ApprovalModel
        from services.storage.models.base import new_uuid
        approval_id = new_uuid()
        with get_session() as s:
            approval = ApprovalModel(
                id=approval_id,
                action="inbound_response",
                details={
                    "lead_id":   lead_id,
                    "lead_name": getattr(lead, "name", ""),
                    "lead_name": getattr(lead, "name", ""),
                    "body":      getattr(lead, "outreach_draft", ""),
                    "channel":   getattr(lead, "source_type", "") or "whatsapp",
                },
                risk_level=2,
                status="pending",
                requested_by="lead_acquisition_engine",
            )
            s.add(approval)
    except Exception as e:
        log.warning(f"[_create_approval_for_inbound] failed: {e}")
        return

    # Send Telegram approval request (non-blocking, best-effort)
    if approval_id:
        _telegram_send_approval(
            lead=lead,
            draft=getattr(lead, "outreach_draft", ""),
            approval_id=approval_id,
            action_label="inbound_response",
            channel=getattr(lead, "source_type", "") or "whatsapp",
        )


def _telegram_hot_lead_alert(lead: Any, score: int, source: str) -> None:
    """Push a simple Telegram alert for a newly discovered hot lead."""
    try:
        from services.telegram_service import telegram_service
        name  = getattr(lead, "name", "לא ידוע")
        city  = getattr(lead, "city", "") or ""
        phone = getattr(lead, "phone", "") or ""
        text  = (
            f"🔥 *ליד חם נגלה*\n\n"
            f"👤 {name}  |  🏙️ {city}\n"
            f"📞 {phone}\n"
            f"⭐ ציון: {score}/100  |  מקור: {source}"
        )
        telegram_service.send(text)
    except Exception as e:
        log.debug(f"[_telegram_hot_lead_alert] non-critical: {e}")


def _telegram_send_approval(lead: Any, draft: str, approval_id: str,
                             action_label: str, channel: str) -> None:
    """Send Telegram approval card with approve/deny/edit buttons."""
    try:
        from services.telegram_service import telegram_service
        name = getattr(lead, "name", "לא ידוע")
        score = getattr(lead, "score", 0) or 0
        telegram_service.send_approval_request(
            action=action_label,
            preview=draft[:300] if draft else "(אין טיוטה)",
            approval_id=approval_id,
            lead_name=f"{name} (ציון {score})",
            channel=channel,
        )
    except Exception as e:
        log.debug(f"[_telegram_send_approval] non-critical: {e}")
