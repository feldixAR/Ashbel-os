"""
POST /api/command

Accepts a natural-language command in Hebrew or English,
passes it to the orchestrator, and returns OrchestratorResult.

Request body:
    { "command": "תוסיף ליד יוסי כהן מתל אביב טלפון 0501234567" }

Response:
    {
      "success": true,
      "data": {
        "intent":         "add_lead",
        "message":        "ליד נוצר בהצלחה: יוסי כהן",
        "task_id":        "...",
        "trace_id":       "...",
        "needs_approval": false,
        "output":         { ... }
      }
    }
"""

import logging
from flask import Blueprint, request
from api.middleware import require_auth, log_request, ok, _error

log = logging.getLogger(__name__)
bp  = Blueprint("commands", __name__)


@bp.route("/command", methods=["POST"])
@require_auth
@log_request
def post_command():
    body    = request.get_json(silent=True) or {}
    command = (body.get("command") or "").strip()

    if not command:
        return _error("field 'command' is required", 400)

    from orchestration.orchestrator import orchestrator
    result = orchestrator.handle_command(command)

    return ok({
        "intent":         result.intent,
        "message":        result.message,
        "task_id":        result.task_id,
        "trace_id":       result.trace_id,
        "needs_approval": result.needs_approval,
        "approval_id":    result.approval_id,
        "output":         result.data,
        "error":          result.error,
    })
