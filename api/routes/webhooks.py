"""
api/routes/webhooks.py — WhatsApp Business API webhook handler.

GET  /api/webhooks/whatsapp   webhook verification (Meta hub.verify_token challenge)
POST /api/webhooks/whatsapp   inbound messages & status updates
"""

import logging

from flask import Blueprint, request

from api.middleware import ok, _error
from services.integrations.whatsapp_business import wa_business

log = logging.getLogger(__name__)
bp  = Blueprint("webhooks", __name__)


# ── Webhook verification ────────────────────────────────────────────────────────

@bp.route("/webhooks/whatsapp", methods=["GET"])
def verify_whatsapp_webhook():
    """
    Meta sends GET with hub.mode=subscribe, hub.challenge, hub.verify_token.
    Return hub.challenge as plain text to confirm ownership.
    """
    mode      = request.args.get("hub.mode")
    challenge = request.args.get("hub.challenge")
    token     = request.args.get("hub.verify_token")

    ok_flag, echo = wa_business.verify_webhook(mode, token, challenge)
    if ok_flag:
        log.info("[Webhook] WhatsApp webhook verified ✓")
        return echo, 200, {"Content-Type": "text/plain"}
    log.warning(f"[Webhook] Verification failed — mode={mode} token={token}")
    return _error("verification failed", 403)


# ── Inbound event handler ───────────────────────────────────────────────────────

@bp.route("/webhooks/whatsapp", methods=["POST"])
def receive_whatsapp_event():
    """
    Receive WhatsApp Business API events (messages, statuses, reactions).
    Parse → persist MessageModel → optionally trigger orchestrator reply.
    Always returns HTTP 200 to Meta (otherwise retries flood in).
    """
    payload = request.get_json(silent=True) or {}
    try:
        events = wa_business.parse_events(payload)
        if not events:
            return ok({"received": 0})

        processed = 0
        for ev in events:
            try:
                _handle_event(ev)
                processed += 1
            except Exception as inner:
                log.error(f"[Webhook] event handling failed: {inner}", exc_info=True)

        return ok({"received": len(events), "processed": processed})
    except Exception as e:
        log.error(f"[Webhook] parse error: {e}", exc_info=True)
        # Still return 200 — Meta must not retry
        return ok({"error": str(e), "received": 0})


# ── Internal dispatcher ─────────────────────────────────────────────────────────

def _handle_event(ev) -> None:
    """
    Route a single WAEvent to the appropriate handler.
    Supported types: message, status
    """
    if ev.event_type == "message":
        _handle_inbound_message(ev)
    elif ev.event_type == "status":
        _handle_status_update(ev)
    else:
        log.debug(f"[Webhook] unhandled event type: {ev.event_type}")


def _handle_inbound_message(ev) -> None:
    """Persist an inbound WhatsApp message to MessageModel."""
    from services.storage.db import get_session
    from services.storage.models.message import MessageModel
    from services.storage.models.base import new_uuid
    import datetime, pytz

    _IL = pytz.timezone("Asia/Jerusalem")
    now_il = datetime.datetime.now(_IL).isoformat()

    # Try to resolve lead by phone
    lead_id = _resolve_lead_by_phone(ev.phone)

    with get_session() as s:
        s.add(MessageModel(
            id=new_uuid(),
            lead_id=lead_id or "",
            channel="whatsapp",
            direction="inbound",
            body=ev.body or "",
            provider_message_id=ev.message_id or "",
            status="received",
            sent_at_il=now_il,
            raw_payload=str(ev.raw or ""),
        ))

    # Mark as read via API
    if ev.message_id:
        try:
            wa_business.mark_read(ev.message_id)
        except Exception as e:
            log.warning(f"[Webhook] mark_read failed: {e}")

    # Update lead.last_contact if resolved
    if lead_id:
        _touch_lead_contact(lead_id, now_il[:10])

    log.info(f"[Webhook] inbound msg from {ev.phone} → lead={lead_id or 'unknown'}")


def _handle_status_update(ev) -> None:
    """Update MessageModel.status based on delivery/read receipts."""
    if not ev.message_id:
        return
    try:
        from services.storage.db import get_session
        from services.storage.models.message import MessageModel
        import datetime, pytz

        _IL = pytz.timezone("Asia/Jerusalem")
        now_il = datetime.datetime.now(_IL).isoformat()

        with get_session() as s:
            msg = (s.query(MessageModel)
                   .filter_by(provider_message_id=ev.message_id)
                   .first())
            if msg:
                msg.status = ev.status or msg.status
                if ev.status == "delivered":
                    msg.delivered_at_il = now_il
                elif ev.status == "read":
                    msg.read_at_il = now_il
        log.debug(f"[Webhook] status update: {ev.message_id} → {ev.status}")
    except Exception as e:
        log.warning(f"[Webhook] _handle_status_update: {e}")


# ── Helpers ─────────────────────────────────────────────────────────────────────

def _resolve_lead_by_phone(phone: str) -> str:
    """Return lead_id matching phone, or empty string if not found."""
    if not phone:
        return ""
    try:
        from services.storage.repositories.lead_repo import LeadRepository
        phone_clean = phone.strip().lstrip("+")
        repo  = LeadRepository()
        leads = repo.list_all()
        lead  = next(
            (l for l in leads
             if l.phone and l.phone.strip().lstrip("+").endswith(phone_clean[-9:])),
            None,
        )
        return lead.id if lead else ""
    except Exception as e:
        log.warning(f"[Webhook] _resolve_lead_by_phone: {e}")
        return ""


def _touch_lead_contact(lead_id: str, date_str: str) -> None:
    try:
        from services.storage.db import get_session
        from services.storage.models.lead import LeadModel
        with get_session() as s:
            lead = s.query(LeadModel).filter_by(id=lead_id).first()
            if lead:
                lead.last_contact = date_str
    except Exception as e:
        log.warning(f"[Webhook] _touch_lead_contact: {e}")
