"""
system.py — GET /api/health, GET /api/status, GET /api/version
"""
import logging
import os
from pathlib import Path
from flask import Blueprint
from api.middleware import require_auth, log_request, ok

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


def _scheduler_status() -> dict:
    try:
        from scheduler.revenue_scheduler import status
        return status()
    except Exception:
        return {"running": False, "jobs": []}

