"""
agents.py — GET /api/agents
"""
import logging
from flask import Blueprint, request
from api.middleware import require_auth, log_request, ok

log = logging.getLogger(__name__)
bp  = Blueprint("agents", __name__)


@bp.route("/agents", methods=["GET"])
@require_auth
@log_request
def list_agents():
    from services.storage.repositories.agent_repo import AgentRepository
    department = request.args.get("department")
    agents     = AgentRepository().get_active(department=department)
    return ok({
        "agents": [_serialize_agent(a) for a in agents],
        "total":  len(agents),
    })


def _serialize_agent(a) -> dict:
    return {
        "id":               a.id,
        "name":             a.name,
        "role":             a.role,
        "department":       a.department,
        "active_version":   a.active_version,
        "model_preference": a.model_preference,
        "tasks_done":       a.tasks_done,
        "last_active_at":   a.last_active_at,
    }
