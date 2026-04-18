"""
channels.py — Channel readiness API.

GET  /api/channels/status           — all channel statuses
GET  /api/channels/status/<channel> — single channel status
POST /api/channels/draft            — generate channel draft + manual send instructions
POST /api/channels/select           — select best channel for a lead
"""
import logging
from flask import Blueprint, request
from api.middleware import require_auth, log_request, ok, _error

log = logging.getLogger(__name__)
bp  = Blueprint("channels", __name__)


@bp.route("/channels/status", methods=["GET"])
@require_auth
@log_request
def all_statuses():
    from services.channels.channel_router import all_channel_statuses
    statuses = all_channel_statuses()
    return ok({"channels": statuses, "count": len(statuses)})


@bp.route("/channels/status/<channel>", methods=["GET"])
@require_auth
@log_request
def channel_status(channel: str):
    from services.channels.channel_router import get_channel_status
    status = get_channel_status(channel)
    return ok(status)


@bp.route("/channels/draft", methods=["POST"])
@require_auth
@log_request
def draft_for_channel():
    body    = request.get_json(silent=True) or {}
    channel = (body.get("channel") or "whatsapp").lower()
    lead    = body.get("lead") or {}
    message = body.get("message") or body.get("body") or ""
    subject = body.get("subject") or ""

    if not lead and body.get("lead_id"):
        try:
            from services.storage.repositories.lead_repo import LeadRepository
            lead_obj = LeadRepository().get(body["lead_id"])
            if lead_obj:
                lead = {
                    "name":  lead_obj.name,
                    "phone": getattr(lead_obj, "phone", ""),
                    "email": getattr(lead_obj, "email", ""),
                }
        except Exception:
            pass

    if not message:
        return _error("field 'message' required", 400)

    try:
        from services.channels.channel_router import draft_for_channel as _draft
        from config.business_registry import get_active_business
        profile = get_active_business()
        result  = _draft(channel, lead, message, subject, profile.name)
        return ok(result.to_dict())
    except Exception as e:
        log.error(f"[channels/draft] {e}", exc_info=True)
        return _error(str(e), 500)


@bp.route("/channels/select", methods=["POST"])
@require_auth
@log_request
def select_channel():
    body = request.get_json(silent=True) or {}
    lead = body.get("lead") or {}

    if not lead and body.get("lead_id"):
        try:
            from services.storage.repositories.lead_repo import LeadRepository
            lead_obj = LeadRepository().get(body["lead_id"])
            if lead_obj:
                lead = {
                    "name":  lead_obj.name,
                    "phone": getattr(lead_obj, "phone", ""),
                    "email": getattr(lead_obj, "email", ""),
                }
        except Exception:
            pass

    try:
        from services.channels.channel_router import channel_router
        from config.business_registry import get_active_business
        profile  = get_active_business()
        channel  = channel_router.select(lead, profile)
        status   = channel_router.status(channel)
        return ok({"channel": channel, "status": status})
    except Exception as e:
        log.error(f"[channels/select] {e}", exc_info=True)
        return _error(str(e), 500)


@bp.route("/channels/manual", methods=["POST"])
@require_auth
@log_request
def manual_send_workflow():
    """Generate complete manual send package for any channel."""
    body      = request.get_json(silent=True) or {}
    channel   = body.get("channel", "whatsapp")
    lead_name = body.get("lead_name") or body.get("name") or ""
    contact   = body.get("contact") or body.get("phone") or body.get("email") or ""
    message   = body.get("message") or body.get("body") or ""
    subject   = body.get("subject") or ""

    if not message:
        return _error("field 'message' required", 400)

    try:
        from services.channels.manual_send import generate_manual_workflow
        result = generate_manual_workflow(channel, lead_name, contact, message, subject)
        return ok(result.to_dict())
    except Exception as e:
        log.error(f"[channels/manual] {e}", exc_info=True)
        return _error(str(e), 500)


@bp.route("/marketing/weekly", methods=["GET"])
@require_auth
@log_request
def marketing_weekly():
    """GET /api/marketing/weekly — this week's marketing recommendations."""
    try:
        from engines.marketing_engine import generate_weekly_plan
        plan = generate_weekly_plan()
        return ok({
            "week_start":     plan.week_start,
            "business":       plan.business_name,
            "recommendations": [
                {"category": r.category, "title": r.title, "body": r.body,
                 "channel": r.channel, "cta": r.cta}
                for r in plan.recommendations
            ],
            "post_drafts":    plan.post_drafts,
            "campaign_ideas": plan.campaign_ideas,
            "seasonal_notes": plan.seasonal_notes,
        })
    except Exception as e:
        log.error(f"[marketing/weekly] {e}", exc_info=True)
        return _error(str(e), 500)
