from flask import Blueprint, request, jsonify
import logging, uuid as _uuid
from api.middleware import require_auth, ok, _error
log = logging.getLogger(__name__)
bp = Blueprint("outreach", __name__)

@bp.route("/outreach/queue", methods=["GET"])
def get_outreach_queue():
    try:
        from engines.outreach_engine import build_outreach_queue, prioritize_daily
        from services.storage.repositories.lead_repo import LeadRepository
        leads = LeadRepository().list_all(); queue = build_outreach_queue(leads); daily = prioritize_daily(queue)
        return jsonify({"success": True, "total_queue": len(queue), "daily_count": len(daily), "daily_tasks": [{"task_id": t.task_id, "lead_name": t.lead_name, "phone": t.phone, "channel": t.channel, "message": t.message, "audience": t.audience, "priority": t.priority, "urgency": t.urgency, "reason": t.reason, "attempt": t.attempt, "deep_link": t.deep_link} for t in daily]})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@bp.route("/outreach/summary", methods=["GET"])
def get_daily_summary():
    try:
        from engines.outreach_engine import daily_outreach_summary
        s = daily_outreach_summary()
        return jsonify({"success": True, "date": s.date, "total_due": s.total_due, "pending": s.pending, "overdue": s.overdue, "top_priorities": [{"lead_name": t.lead_name, "phone": t.phone, "message": t.message[:100], "urgency": t.urgency, "reason": t.reason, "deep_link": t.deep_link} for t in s.top_priorities], "pipeline": [{"outreach_id": p.outreach_id, "lead_name": p.lead_name, "status": p.status, "attempt": p.attempt, "next_followup": p.next_followup} for p in s.pipeline]})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@bp.route("/outreach/execute", methods=["POST"])
def execute_task():
    try:
        data = request.get_json() or {}
        from engines.outreach_engine import OutreachTask, execute_outreach, record_outreach_sent
        task = OutreachTask(task_id=data.get("task_id", str(_uuid.uuid4())), lead_id=data.get("lead_id",""), lead_name=data.get("lead_name",""), phone=data.get("phone",""), channel=data.get("channel","whatsapp"), message=data.get("message",""), audience=data.get("audience","general"), priority=data.get("priority",2), urgency=data.get("urgency","today"), reason=data.get("reason",""), goal_id=data.get("goal_id",""), opp_id=data.get("opp_id",""), attempt=data.get("attempt",1), deep_link=data.get("deep_link",""))
        result = execute_outreach(task)
        if result.success and task.lead_id: record_outreach_sent(task)
        return jsonify({"success": result.success, "lead_name": result.lead_name, "mode": result.mode, "message_id": result.message_id, "deep_link": result.deep_link, "sent_at": result.sent_at, "error": result.error})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@bp.route("/outreach/send", methods=["POST"])
def send_to_lead():
    try:
        data = request.get_json() or {}
        name = data.get("name",""); phone = data.get("phone",""); message = data.get("message",""); lead_id = data.get("lead_id","")
        if not phone and name:
            from services.storage.repositories.lead_repo import LeadRepository
            for l in LeadRepository().list_all():
                if name.lower() in l.name.lower(): phone = l.phone or ""; lead_id = l.id; break
        if not phone: return jsonify({"success": False, "error": "לא נמצא טלפון"}), 400
        if not message: return jsonify({"success": False, "error": "חסרה הודעה"}), 400
        from engines.outreach_engine import _build_whatsapp_link, OutreachTask, execute_outreach
        task = OutreachTask(task_id=str(_uuid.uuid4()), lead_id=lead_id, lead_name=name, phone=phone, channel="whatsapp", message=message, audience="general", priority=1, urgency="today", reason="שליחה ידנית", attempt=1, deep_link=_build_whatsapp_link(phone, message))
        result = execute_outreach(task)
        return jsonify({"success": result.success, "lead_name": name, "phone": phone, "mode": result.mode, "deep_link": result.deep_link, "message_id": result.message_id, "sent_at": result.sent_at})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@bp.route("/outreach/<outreach_id>/status", methods=["PUT"])
def update_status(outreach_id):
    try:
        data = request.get_json() or {}
        from engines.outreach_engine import update_pipeline_status
        ok = update_pipeline_status(outreach_id, data.get("status","sent"), data.get("notes",""))
        return jsonify({"success": ok, "outreach_id": outreach_id, "status": data.get("status")})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@bp.route("/outreach/pipeline", methods=["GET"])
def get_pipeline():
    try:
        from services.storage.repositories.outreach_repo import OutreachRepository
        records = OutreachRepository().list_due_followup()
        return jsonify({"success": True, "count": len(records), "pipeline": [r.to_dict() for r in records]})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

# ── Batch 9: Lifecycle endpoints ──────────────────────────────────────────────

@bp.route("/outreach/<record_id>/status", methods=["POST"])
@require_auth
def update_lifecycle_status(record_id: str):
    """
    POST /api/outreach/<record_id>/status
    Body: {"lifecycle_status": "closed_won", "notes": "optional"}

    Transition a growth outreach record's lifecycle_status via the FSM.
    Valid states: sent | awaiting_response | followup_due | followup_sent |
                  closed_won | closed_lost
    """
    body            = request.get_json(silent=True) or {}
    target_status   = (body.get("lifecycle_status") or "").strip()
    notes           = (body.get("notes") or "").strip()

    if not target_status:
        return _error("'lifecycle_status' field is required", 400)

    from services.storage.repositories.outreach_repo import OutreachRepository
    from services.growth.policy import validate_transition

    repo   = OutreachRepository()
    record = repo.get_by_id(record_id)
    if not record:
        return _error(f"record '{record_id}' not found", 404)

    current = record.lifecycle_status or "sent"
    ok_flag, err_msg = validate_transition(current, target_status)
    if not ok_flag:
        return _error(err_msg, 422)

    success = repo.set_lifecycle_status(record_id, target_status, notes)
    if not success:
        return _error("DB update failed", 500)

    log.info(
        f"[Outreach] lifecycle transition record={record_id} "
        f"{current} → {target_status}"
    )
    return ok({
        "record_id":        record_id,
        "previous_status":  current,
        "lifecycle_status": target_status,
        "notes":            notes,
    })


@bp.route("/outreach/followups", methods=["GET"])
@require_auth
def list_followup_due():
    """GET /api/outreach/followups — list records where lifecycle_status=followup_due."""
    from services.storage.repositories.outreach_repo import OutreachRepository
    records = OutreachRepository().list_lifecycle_due(limit=50)
    return ok({
        "count":   len(records),
        "records": [r.to_dict() for r in records],
    })


@bp.route("/outreach/followups/process", methods=["POST"])
@require_auth
def run_followup_engine():
    """
    POST /api/outreach/followups/process
    Step 1: promote awaiting_response records past next_action_at → followup_due.
    Step 2: generate reminder assets for all followup_due records.
    Records are created with status=ready. Dispatch is human-in-the-loop.
    """
    from services.growth.followup_engine import process_pending_followups, promote_overdue_records
    promoted = promote_overdue_records()          # must run first
    results  = process_pending_followups(limit=20)
    succeeded = [r for r in results if r.success]
    failed    = [r for r in results if not r.success]
    return ok({
        "promoted":  promoted,
        "processed": len(results),
        "succeeded": len(succeeded),
        "failed":    len(failed),
        "results":   [r.to_dict() for r in results],
    })


@bp.route("/outreach/request-approval", methods=["POST"])
@require_auth
def request_outreach_approval():
    """
    POST /api/outreach/request-approval
    Create an ApprovalModel for a pending outreach action.
    The approval.details.outreach_task payload is what gets executed
    when the approval is resolved as 'approve' via POST /api/approvals/<id>.

    Body: {
      "lead_id":   "...",
      "lead_name": "...",
      "phone":     "...",
      "message":   "...",
      "channel":   "whatsapp",   (optional, default whatsapp)
      "audience":  "general",    (optional)
      "attempt":   1,            (optional)
      "risk_level": 1            (optional, 0-3)
    }
    """
    data = request.get_json(silent=True) or {}
    lead_id   = (data.get("lead_id")   or "").strip()
    lead_name = (data.get("lead_name") or "").strip()
    phone     = (data.get("phone")     or "").strip()
    message   = (data.get("message")   or "").strip()

    if not lead_id or not phone or not message:
        return _error("lead_id, phone, and message are required", 400)

    channel   = data.get("channel",   "whatsapp")
    audience  = data.get("audience",  "general")
    attempt   = int(data.get("attempt", 1))
    risk_level= int(data.get("risk_level", 1))

    from services.storage.repositories.approval_repo import ApprovalRepository
    approval = ApprovalRepository().create(
        action    = f"שליחת {channel} ל-{lead_name}",
        details   = {
            "outreach_task": {
                "lead_id":   lead_id,
                "lead_name": lead_name,
                "phone":     phone,
                "message":   message,
                "channel":   channel,
                "audience":  audience,
                "attempt":   attempt,
            }
        },
        risk_level = risk_level,
        task_id    = None,
        requested_by = "operator",
    )
    log.info(f"[Outreach] approval requested id={approval.id} lead={lead_id}")
    return ok({
        "approval_id": approval.id,
        "action":      approval.action,
        "status":      approval.status,
        "risk_level":  approval.risk_level,
    })


@bp.route("/outreach/lifecycle/<lifecycle_status>", methods=["GET"])
@require_auth
def list_by_lifecycle(lifecycle_status: str):
    """GET /api/outreach/lifecycle/<status> — list records by lifecycle_status."""
    from services.storage.repositories.outreach_repo import OutreachRepository
    from services.growth.policy import ALL_STATES
    if lifecycle_status not in ALL_STATES:
        return _error(f"unknown status '{lifecycle_status}'", 400)
    records = OutreachRepository().list_by_lifecycle(lifecycle_status, limit=50)
    return ok({
        "lifecycle_status": lifecycle_status,
        "count":            len(records),
        "records":          [r.to_dict() for r in records],
    })


@bp.route("/outreach/daily", methods=["POST"])
def run_daily_cycle():
    try:
        from engines.outreach_engine import build_outreach_queue, prioritize_daily, execute_outreach, record_outreach_sent
        from services.storage.repositories.lead_repo import LeadRepository
        leads = LeadRepository().list_all(); queue = build_outreach_queue(leads); daily = prioritize_daily(queue, 5)
        results = []
        for task in daily:
            result = execute_outreach(task)
            if result.success and task.lead_id: record_outreach_sent(task)
            results.append({"lead_name": task.lead_name, "mode": result.mode, "deep_link": result.deep_link, "message_id": result.message_id, "success": result.success})
        return jsonify({"success": True, "total_queue": len(queue), "executed": len(results), "results": results})
    except Exception as e:
        log.error(f"[Outreach] daily cycle error: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500
