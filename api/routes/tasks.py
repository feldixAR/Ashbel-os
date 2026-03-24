"""
tasks.py — GET /api/tasks, GET /api/tasks/<id>
"""
import logging
from flask import Blueprint, request
from api.middleware import require_auth, log_request, ok, _error

log = logging.getLogger(__name__)
bp  = Blueprint("tasks", __name__)


@bp.route("/tasks", methods=["GET"])
@require_auth
@log_request
def list_tasks():
    from services.storage.repositories.task_repo import TaskRepository
    status = request.args.get("status", None)
    if status:
        tasks = TaskRepository().get_by_status(status)
    else:
        # Default: last 50 tasks of any status
        repo  = TaskRepository()
        tasks = repo.get_recent(limit=50)
    return ok({
        "tasks": [_serialize_task(t) for t in tasks],
        "total": len(tasks),
    })


@bp.route("/tasks/<task_id>", methods=["GET"])
@require_auth
@log_request
def get_task(task_id: str):
    from services.storage.repositories.task_repo import TaskRepository
    task = TaskRepository().get(task_id)
    if not task:
        return _error(f"task '{task_id}' not found", 404)
    return ok({"task": _serialize_task(task)})


def _serialize_task(t) -> dict:
    return {
        "id":           t.id,
        "type":         t.type,
        "action":       t.action,
        "status":       t.status,
        "priority":     t.priority,
        "risk_level":   t.risk_level,
        "agent_id":     t.agent_id,
        "model_used":   t.model_used,
        "cost_usd":     t.cost_usd,
        "duration_ms":  t.duration_ms,
        "retry_count":  t.retry_count,
        "output_data":  t.output_data,
        "last_error":   t.last_error,
        "created_at":   str(t.created_at) if t.created_at else None,
        "completed_at": t.completed_at,
    }
