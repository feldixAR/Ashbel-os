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

    return ok({"approval": _serialize(result)})


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
    }
