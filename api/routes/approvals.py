"""
approvals.py — GET /api/approvals, POST /api/approvals/<id>
"""
import logging
from flask import Blueprint, request
from api.middleware import require_auth, log_request, ok, _error

log = logging.getLogger(__name__)
bp  = Blueprint("approvals", __name__)


@bp.route("/approvals", methods=["GET"])
@require_auth
@log_request
def list_approvals():
    from services.storage.repositories.approval_repo import ApprovalRepository
    pending = ApprovalRepository().get_pending()
    return ok({
        "approvals": [_serialize(a) for a in pending],
        "total":     len(pending),
    })


@bp.route("/approvals/history", methods=["GET"])
@require_auth
@log_request
def approval_history():
    limit = min(int(request.args.get("limit", 50)), 200)
    from services.storage.repositories.approval_repo import ApprovalRepository
    resolved = ApprovalRepository().get_resolved(limit=limit)
    return ok({
        "history": [_serialize(a) for a in resolved],
        "total":   len(resolved),
    })


@bp.route("/approvals/create", methods=["POST"])
@require_auth
@log_request
def create_approval():
    """Create a pending approval — used by DraftModal and other UI surfaces."""
    body = request.get_json(silent=True) or {}
    action     = (body.get("action") or "send_outreach").strip()
    risk_level = int(body.get("risk_level") or 2)
    lead_id    = body.get("lead_id") or ""
    details    = {
        "lead_id":      lead_id,
        "lead_name":    body.get("lead_name") or "",
        "draft_body":   body.get("draft_body") or "",
        "draft_subject": body.get("draft_subject") or "",
        "channel":      body.get("channel") or "",
        "action_type":  body.get("action_type") or "",
        "rationale":    body.get("rationale") or "",
    }
    try:
        from services.storage.repositories.approval_repo import ApprovalRepository
        approval = ApprovalRepository().create(
            action=action,
            details=details,
            risk_level=risk_level,
            task_id=None,
            requested_by="ui",
        )
        return ok({"id": approval.id, "status": approval.status})
    except Exception as e:
        log.error(f"[approvals/create] {e}", exc_info=True)
        return _error(str(e), 500)


@bp.route("/approvals/<approval_id>", methods=["POST"])
@require_auth
@log_request
def resolve_approval(approval_id: str):
    body   = request.get_json(silent=True) or {}
    action = (body.get("action") or "").strip()

    if action not in ("approve", "deny"):
        return _error("field 'action' must be 'approve' or 'deny'", 400)

    from services.storage.repositories.approval_repo import ApprovalRepository
    from events.event_bus                             import event_bus
    import events.event_types                         as ET

    repo   = ApprovalRepository()
    status = "approved" if action == "approve" else "denied"
    result = repo.resolve(approval_id, status=status, resolved_by="owner",
                           note=body.get("note", ""))

    if not result:
        return _error(f"approval '{approval_id}' not found or already resolved", 404)

    event_type = ET.APPROVAL_GRANTED if action == "approve" else ET.APPROVAL_DENIED
    event_bus.publish(event_type, payload={
        "approval_id": approval_id,
        "action":      result.action,
        "resolved_by": "owner",
        "task_id":     result.task_id,
    })

    # ── Approval-driven outreach execution ───────────────────────────────────
    # If details contains outreach_task and action=approve → execute immediately.
    exec_result = None
    if action == "approve":
        details = result.details or {}
        ot = details.get("outreach_task") if isinstance(details, dict) else None
        if ot and isinstance(ot, dict) and ot.get("lead_id") and ot.get("phone"):
            try:
                import uuid as _uuid
                from engines.outreach_engine import (
                    OutreachTask, execute_outreach,
                    record_outreach_sent, record_outreach_failed,
                    _build_whatsapp_link,
                )
                msg  = ot.get("message", "")
                task = OutreachTask(
                    task_id  = str(_uuid.uuid4()),
                    lead_id  = ot["lead_id"],
                    lead_name= ot.get("lead_name", ""),
                    phone    = ot["phone"],
                    channel  = ot.get("channel", "whatsapp"),
                    message  = msg,
                    audience = ot.get("audience", "general"),
                    priority = ot.get("priority", 1),
                    urgency  = "today",
                    reason   = f"אושר על-ידי בעלים (approval {approval_id[:8]})",
                    attempt  = ot.get("attempt", 1),
                    deep_link= _build_whatsapp_link(ot["phone"], msg),
                )
                res = execute_outreach(task)
                exec_result = {"executed": True, "mode": res.mode, "success": res.success}
                if res.success:
                    record_outreach_sent(task, mode=res.mode)
                else:
                    record_outreach_failed(task, error=res.error or "execution failed")
                log.info(f"[Approvals] post-approval outreach lead={task.lead_id} mode={res.mode}")
            except Exception as ex:
                log.error(f"[Approvals] post-approval execution error: {ex}")
                exec_result = {"executed": False, "error": str(ex)}

    resp = {"approval": _serialize(result)}
    if exec_result:
        resp["outreach_execution"] = exec_result
    return ok(resp)


def _resolve_approval(approval_id: str, action: str, source: str = "api") -> str:
    """
    Shared resolution logic callable from telegram webhook (no HTTP context).
    Returns a human-readable Hebrew result string.
    """
    from services.storage.repositories.approval_repo import ApprovalRepository
    from events.event_bus                             import event_bus
    import events.event_types                         as ET

    repo   = ApprovalRepository()
    status = "approved" if action == "approve" else "denied"
    result = repo.resolve(approval_id, status=status, resolved_by=source, note="")

    if not result:
        return f"❌ אישור `{approval_id[:8]}` לא נמצא או כבר טופל"

    event_type = ET.APPROVAL_GRANTED if action == "approve" else ET.APPROVAL_DENIED
    event_bus.publish(event_type, payload={
        "approval_id": approval_id,
        "action":      result.action,
        "resolved_by": source,
        "task_id":     result.task_id,
    })

    if action == "approve":
        details = result.details or {}
        ot = details.get("outreach_task") if isinstance(details, dict) else None
        if ot and isinstance(ot, dict) and ot.get("lead_id") and ot.get("phone"):
            try:
                import uuid as _uuid
                from engines.outreach_engine import (
                    OutreachTask, execute_outreach,
                    record_outreach_sent, record_outreach_failed,
                    _build_whatsapp_link,
                )
                msg  = ot.get("message", "")
                task = OutreachTask(
                    task_id  = str(_uuid.uuid4()),
                    lead_id  = ot["lead_id"],
                    lead_name= ot.get("lead_name", ""),
                    phone    = ot["phone"],
                    channel  = ot.get("channel", "whatsapp"),
                    message  = msg,
                    audience = ot.get("audience", "general"),
                    priority = ot.get("priority", 1),
                    urgency  = "today",
                    reason   = f"אושר דרך {source}",
                    attempt  = ot.get("attempt", 1),
                    deep_link= _build_whatsapp_link(ot["phone"], msg),
                )
                res = execute_outreach(task)
                if res.success:
                    record_outreach_sent(task, mode=res.mode)
                    # ── Live learning: record template sent ───────────────
                    try:
                        from skills.learning_skills import record_template_outcome
                        record_template_outcome(
                            template_type="outreach",
                            template_text=msg[:500],
                            outcome="sent",
                            segment=ot.get("audience"),
                            channel=ot.get("channel"),
                        )
                    except Exception:
                        pass
                    return f"✅ אושר ובוצע — {ot.get('lead_name','')} ({res.mode})"
                else:
                    record_outreach_failed(task, error=res.error or "failed")
                    return f"✅ אושר אך ביצוע נכשל: {res.error}"
            except Exception as ex:
                return f"✅ אושר אך שגיאת ביצוע: {ex}"

        # Lead ops approval format: {lead_id, lead_name, body, channel, action_type}
        lead_id   = details.get("lead_id") if isinstance(details, dict) else None
        lead_name = details.get("lead_name", "") if isinstance(details, dict) else ""
        body      = details.get("body", "")      if isinstance(details, dict) else ""
        channel   = details.get("channel", "")   if isinstance(details, dict) else ""
        if lead_id and body:
            try:
                import datetime as _dt
                from services.storage.db import get_session
                from services.storage.models.activity import ActivityModel
                with get_session() as s:
                    s.add(ActivityModel(
                        lead_id=lead_id,
                        activity_type="note",
                        subject=f"הודעת פנייה אושרה — {channel}",
                        notes=body[:500],
                        outcome="completed",
                        performed_by=source,
                    ))
                event_bus.publish(
                    ET.LEAD_OUTREACH_SENT,
                    payload={"lead_id": lead_id, "lead_name": lead_name,
                             "channel": channel, "approval_id": approval_id},
                )
                return f"✅ אושר ונרשם — {lead_name}"
            except Exception as ex:
                return f"✅ אושר אך רישום נכשל: {ex}"

        # System change approval: create feature branch + store execution plan
        change_type = details.get("change_type") if isinstance(details, dict) else None
        if change_type:
            try:
                import subprocess
                import os as _os
                repo_root = _os.path.abspath(
                    _os.path.join(_os.path.dirname(__file__), "..", "..")
                )
                branch = f"feat/system-change-{approval_id[:8]}"
                r = subprocess.run(
                    ["git", "checkout", "-b", branch],
                    cwd=repo_root, capture_output=True, timeout=15, text=True,
                )
                from memory.memory_store import MemoryStore
                MemoryStore.write("global", f"pending_change_{approval_id[:8]}", {
                    "branch":        branch,
                    "approval_id":   approval_id,
                    "change_type":   change_type,
                    "request":       details.get("request", ""),
                    "plan":          details.get("implementation_plan", ""),
                    "affected_files": details.get("affected_files", []),
                    "status":        "approved_pending_implementation",
                }, updated_by="approval_system")
                if r.returncode == 0:
                    return f"✅ שינוי מערכת אושר — ענף `{branch}` נוצר. ממתין לביצוע."
                else:
                    # Branch may already exist; still store the plan
                    return f"✅ שינוי מערכת אושר. תוכנית שמורה (ענף: {branch})."
            except Exception as ex:
                return f"✅ אושר. שגיאה ביצירת ענף: {ex}"

        return f"✅ אישור {approval_id[:8]} אושר"

    return f"❌ אישור {approval_id[:8]} נדחה"


def _serialize(a) -> dict:
    return {
        "id":          a.id,
        "task_id":     a.task_id,
        "action":      a.action,
        "risk_level":  a.risk_level,
        "status":      a.status,
        "requested_by":a.requested_by,
        "resolved_by": a.resolved_by,
        "resolved_at": a.resolved_at,
        "created_at":  str(a.created_at) if a.created_at else None,
        "details":     a.details or {},   # includes outreach_task when present
    }
