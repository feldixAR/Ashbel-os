"""
system.py — GET /api/health, GET /api/status
"""
import logging
from flask import Blueprint
from api.middleware import require_auth, log_request, ok

log = logging.getLogger(__name__)
bp  = Blueprint("system", __name__)


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


def _scheduler_status() -> dict:
    try:
        from scheduler.revenue_scheduler import status
        return status()
    except Exception:
        return {"running": False, "jobs": []}
