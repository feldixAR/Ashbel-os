"""
api/routes/briefing.py — Live Client Briefing endpoints.

POST  /api/briefing/identify              phone → CallerIdentity
GET   /api/briefing/summary/<lead_id>     full customer summary card
GET   /api/briefing/context/<lead_id>     last N timeline events
POST  /api/briefing/call/start            open call session
POST  /api/briefing/call/end              close call + persist activity
"""

import logging

from flask import Blueprint, request

from api.middleware import require_auth, log_request, ok, _error

log = logging.getLogger(__name__)
bp  = Blueprint("briefing", __name__)


# ── Identify caller ─────────────────────────────────────────────────────────────

@bp.route("/briefing/identify", methods=["POST"])
@require_auth
@log_request
def identify():
    """
    Body: {"phone": "+972501234567"}
    Returns CallerIdentity — identified flag, lead details, open deal count.
    """
    body  = request.get_json(silent=True) or {}
    phone = body.get("phone", "").strip()
    if not phone:
        return _error("phone is required", 400)

    from services.crm.client_briefing import identify_caller
    identity = identify_caller(phone)
    return ok(identity.to_dict())


# ── Customer summary ────────────────────────────────────────────────────────────

@bp.route("/briefing/summary/<lead_id>", methods=["GET"])
@require_auth
@log_request
def customer_summary(lead_id: str):
    """
    Rich summary card: name, status, sector, open deals, last interaction,
    key notes, recent message count.
    """
    from services.crm.client_briefing import get_customer_summary
    summary = get_customer_summary(lead_id)
    return ok(summary.to_dict())


# ── Context retrieval ───────────────────────────────────────────────────────────

@bp.route("/briefing/context/<lead_id>", methods=["GET"])
@require_auth
@log_request
def retrieve_context(lead_id: str):
    """
    Returns last N timeline events for quick pre-call context.
    Query param: limit (default 5, max 20)
    """
    limit  = min(int(request.args.get("limit", 5)), 20)
    from services.crm.client_briefing import retrieve_context as _ctx
    events = _ctx(lead_id, limit=limit)
    return ok({
        "lead_id": lead_id,
        "total":   len(events),
        "events":  [e.to_dict() for e in events],
    })


# ── Call session management ─────────────────────────────────────────────────────

@bp.route("/briefing/call/start", methods=["POST"])
@require_auth
@log_request
def start_call():
    """
    Body: {"lead_id": "...", "call_id": "optional-external-id"}
    Opens a call session. Returns CallSession with stub transcript field.
    """
    body    = request.get_json(silent=True) or {}
    lead_id = body.get("lead_id", "").strip()
    if not lead_id:
        return _error("lead_id is required", 400)
    call_id = body.get("call_id", "").strip()

    from services.crm.client_briefing import start_call_session
    session = start_call_session(lead_id, call_id=call_id)
    return ok(session.to_dict(), status=201)


@bp.route("/briefing/call/end", methods=["POST"])
@require_auth
@log_request
def end_call():
    """
    Body:
      {
        "call_id":      "...",
        "notes":        "Summary of conversation",
        "outcome":      "interested | not_interested | follow_up | sale",
        "duration_sec": 180,
        "performed_by": "operator"
      }
    Closes session, persists ActivityModel, updates Lead.last_contact.
    Returns persisted activity dict or 404 if call_id unknown.
    """
    body         = request.get_json(silent=True) or {}
    call_id      = body.get("call_id", "").strip()
    lead_id      = body.get("lead_id", "").strip()   # fallback for multi-worker
    notes        = body.get("notes", "")
    outcome      = body.get("outcome", "")
    duration_sec = int(body.get("duration_sec", 0))
    performed_by = body.get("performed_by", "operator")

    if not call_id and not lead_id:
        return _error("call_id or lead_id is required", 400)

    from services.crm.client_briefing import end_call_session
    result = end_call_session(
        call_id=call_id,
        notes=notes,
        outcome=outcome,
        duration_sec=duration_sec,
        performed_by=performed_by,
        lead_id_fallback=lead_id,
    )
    if result is None:
        return _error(f"call_id '{call_id}' not found or already ended", 404)
    return ok(result)
