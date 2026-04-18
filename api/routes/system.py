"""
system.py — GET /api/health, GET /api/status, GET /api/version,
            GET /api/system/scheduler, POST /api/system/execute_change/<id>
"""
import logging
import os
from pathlib import Path
from flask import Blueprint, request
from api.middleware import require_auth, log_request, ok, _error

log = logging.getLogger(__name__)
bp  = Blueprint("system", __name__)


def _read_commit() -> str:
    """
    קורא commit hash מקובץ COMMIT_HASH שנוצר ב-CI.
    fallback: משתנה סביבה RAILWAY_GIT_COMMIT שמוזרק אוטומטית על ידי Railway.
    """
    commit_file = Path(__file__).parent.parent.parent / "COMMIT_HASH"
    if commit_file.exists():
        value = commit_file.read_text().strip()
        if value:
            return value[:7]

    railway_commit = os.getenv("RAILWAY_GIT_COMMIT_SHA", "")
    if railway_commit:
        return railway_commit[:7]

    return "unknown"


@bp.route("/health", methods=["GET"])
def health():
    """Public endpoint — no auth required."""
    from services.storage.db import health_check
    return ok({"status": "ok", "db": health_check()})


@bp.route("/status", methods=["GET"])
@require_auth
@log_request
def status():
    from services.storage.repositories.agent_repo    import AgentRepository
    from services.storage.repositories.lead_repo     import LeadRepository
    from services.storage.repositories.approval_repo import ApprovalRepository
    from agents.base.agent_registry                  import agent_registry

    agents   = AgentRepository().get_active()
    leads    = LeadRepository().list_all()
    pending  = ApprovalRepository().get_pending()

    by_dept: dict = {}
    for a in agents:
        by_dept.setdefault(a.department, []).append(a.name)

    return ok({
        "agents":            len(agents),
        "leads":             len(leads),
        "pending_approvals": len(pending),
        "departments":       by_dept,
        "registry_count":    agent_registry.count(),
        "scheduler":         _scheduler_status(),
    })


@bp.route("/version", methods=["GET"])
def version():
    """Public endpoint — מחזיר commit hash פעיל ב-runtime."""
    return ok({
        "commit":      _read_commit(),
        "environment": os.getenv("RAILWAY_ENVIRONMENT_NAME", "local"),
        "service":     os.getenv("RAILWAY_SERVICE_NAME", "ashbel-os"),
    })


@bp.route("/system/metrics", methods=["GET"])
@require_auth
@log_request
def system_metrics():
    from observability.metrics import snapshot
    return ok({"metrics": snapshot()})


@bp.route("/system/traces/<trace_id>", methods=["GET"])
@require_auth
@log_request
def system_trace(trace_id: str):
    from observability.tracing import get
    events = get(trace_id)
    if not events:
        from api.middleware import _error
        return _error(f"trace '{trace_id}' not found", 404)
    return ok({"trace_id": trace_id, "events": events})


@bp.route("/system/pending_changes", methods=["GET"])
@require_auth
@log_request
def pending_changes():
    """
    List all approved-but-not-yet-implemented system change plans.
    Allows a new agent session to pick up the implementation work.
    """
    try:
        from memory.memory_store import MemoryStore
        all_keys = MemoryStore.list_namespace("global")
        changes = [
            v for k, v in all_keys.items()
            if k.startswith("pending_change_")
            and isinstance(v, dict)
            and v.get("status") == "approved_pending_implementation"
        ]
        changes.sort(key=lambda c: c.get("approval_id", ""), reverse=True)
        return ok({"pending_changes": changes, "count": len(changes)})
    except Exception as e:
        return ok({"pending_changes": [], "count": 0, "error": str(e)})


@bp.route("/system/scheduler", methods=["GET"])
@require_auth
@log_request
def scheduler_status_endpoint():
    """Return detailed scheduler status: running flag, job list with next-run, last-run history."""
    return ok(_scheduler_status())


@bp.route("/system/execute_change/<change_id>", methods=["POST"])
@require_auth
@log_request
def execute_change(change_id: str):
    """
    Bounded self-evolution implementation pass.
    Applies safe, reversible changes based on the approved plan's change_type:
      - routing_override  → promote_model(task_type, model_key)
      - template_update   → set best template in MemoryStore
      - scoring_weight    → update scoring weight in MemoryStore
      - other             → mark plan_only (manual required)
    Marks the plan as implemented + records audit event.
    """
    import datetime
    from memory.memory_store import MemoryStore

    plan = MemoryStore.read("global", f"pending_change_{change_id}")
    if not plan:
        return _error(f"change '{change_id}' not found", 404)
    if plan.get("status") != "approved_pending_implementation":
        return _error(
            f"change '{change_id}' is not pending (status: {plan.get('status')})", 400
        )

    change_type = plan.get("change_type", "")
    result_msg  = ""
    applied     = False

    try:
        if change_type == "routing_override":
            task_type = plan.get("task_type") or "sales"
            model_key = plan.get("model_key") or "sonnet"
            from skills.learning_skills import promote_model
            promote_model(task_type, model_key, reason=f"system_change_{change_id}")
            result_msg = f"routing override applied: {task_type} → {model_key}"
            applied    = True

        elif change_type == "template_update":
            t_type = plan.get("template_type") or "first_contact"
            t_text = plan.get("template_text") or plan.get("plan", "")
            if t_text:
                MemoryStore.write("messaging", f"best_{t_type}", t_text,
                                  updated_by=f"system_change_{change_id}")
                result_msg = f"template updated: {t_type}"
                applied    = True
            else:
                result_msg = "template_text missing in plan"

        elif change_type == "scoring_weight":
            key   = plan.get("weight_key") or "default"
            value = plan.get("weight_value")
            if value is not None:
                MemoryStore.write("scoring", f"weight_{key}", value,
                                  updated_by=f"system_change_{change_id}")
                result_msg = f"scoring weight updated: {key} = {value}"
                applied    = True
            else:
                result_msg = "weight_value missing in plan"

        else:
            result_msg = f"change_type '{change_type}' requires manual implementation"
            applied    = False

        updated = dict(plan)
        updated["status"]         = "implemented" if applied else "plan_only"
        updated["implemented_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        updated["result"]         = result_msg
        MemoryStore.write("global", f"pending_change_{change_id}", updated,
                          updated_by="execute_change")

        try:
            from events.event_bus import event_bus
            import events.event_types as ET
            event_bus.publish(ET.TASK_COMPLETED, payload={
                "change_id":   change_id,
                "change_type": change_type,
                "applied":     applied,
                "result":      result_msg,
            })
        except Exception:
            pass

        return ok({
            "change_id":   change_id,
            "change_type": change_type,
            "applied":     applied,
            "result":      result_msg,
            "status":      "implemented" if applied else "plan_only",
        })

    except Exception as e:
        log.error(f"[execute_change] {e}", exc_info=True)
        return _error(str(e), 500)


def _scheduler_status() -> dict:
    try:
        from scheduler.revenue_scheduler import status
        return status()
    except Exception:
        return {"running": False, "jobs": [], "last_runs": {}}

