"""
claude_dispatch.py — Execution bridge: AshbelOS → Claude

POST /api/claude/dispatch
GET  /api/claude/tasks/<task_id>
"""
import logging
from flask import Blueprint, request, jsonify
from api.middleware import require_auth

log = logging.getLogger(__name__)
bp  = Blueprint("claude_dispatch", __name__)


def _ok(data: dict, status: int = 200):
    return jsonify({"success": True, **data}), status


def _err(message: str, status: int = 400):
    return jsonify({"success": False, "error": message}), status


# ── POST /api/claude/dispatch ─────────────────────────────────────────────────

@bp.route("/claude/dispatch", methods=["POST"])
@require_auth
def dispatch():
    body = request.get_json(silent=True) or {}

    approved = body.get("approved")
    if approved is not True:
        return _err("approved must be true to dispatch", 400)

    instruction = (body.get("instruction") or "").strip()
    if not instruction:
        return _err("instruction is required", 400)

    from engines.claude_dispatch import dispatch as _dispatch
    result = _dispatch(body)

    http_status = 200 if result["status"] in ("completed", "dispatched") else 400
    return _ok(result, http_status)


# ── GET /api/claude/tasks/<task_id> ──────────────────────────────────────────

@bp.route("/claude/tasks/<task_id>", methods=["GET"])
@require_auth
def get_task(task_id: str):
    from engines.claude_dispatch import get_task as _get_task
    result = _get_task(task_id)
    if result is None:
        return _err("task not found", 404)
    return _ok(result)
