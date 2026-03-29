"""
openclaw.py — Detachable OpenClaw orchestration boundary.

OpenClaw is an external orchestration/control layer.
AshbelOS remains the business core — this route is an intake adapter only.
All business logic stays in AshbelOS engines.

Endpoints:
  POST /api/openclaw/intent    — submit an intent; always creates a preview first
  GET  /api/openclaw/status/<task_id> — poll task status

Flow enforced:
  Intent (here) → Preview (claude_dispatch.preview) →
  Approval (caller calls POST /api/claude/dispatch with sensitive=True + task_id) →
  Execute → Audit Log (orchestration_source=openclaw)

Fallback guarantee:
  If this route is unreachable, /api/claude/preview + /api/claude/dispatch
  remain fully functional as the AshbelOS-native path.
"""
import logging
from flask import Blueprint, request, jsonify
from api.middleware import require_auth

log = logging.getLogger(__name__)
bp  = Blueprint("openclaw", __name__)


def _ok(data: dict, status: int = 200):
    return jsonify({"success": True, **data}), status


def _err(message: str, status: int = 400):
    return jsonify({"success": False, "error": message}), status


@bp.route("/openclaw/intent", methods=["POST"])
@require_auth
def submit_intent():
    """
    OpenClaw submits an intent. AshbelOS creates a preview and returns the plan.
    Execution requires a separate explicit approval call.

    Body:
      instruction  str  required
      repo         str  optional
      branch       str  optional
      allowed_paths list optional
    """
    body = request.get_json(silent=True) or {}
    instruction = (body.get("instruction") or "").strip()
    if not instruction:
        return _err("instruction is required", 400)

    from engines.claude_dispatch import preview as _preview
    from services.storage.repositories.claude_task_repo import ClaudeTaskRepository

    # Tag orchestration source before preview creates the record
    preview_payload = {
        "instruction":   instruction,
        "repo":          body.get("repo"),
        "branch":        body.get("branch"),
        "allowed_paths": body.get("allowed_paths"),
    }
    result = _preview(preview_payload)

    # Tag source immediately after creation
    if result.get("task_id"):
        ClaudeTaskRepository().update(
            result["task_id"],
            orchestration_source="openclaw",
        )
        result["orchestration_source"] = "openclaw"

    http_status = 200 if result.get("status") == "preview_pending" else 400
    return _ok({
        "task_id":              result.get("task_id"),
        "status":               result.get("status"),
        "preview_plan":         result.get("preview_plan"),
        "orchestration_source": result.get("orchestration_source", "openclaw"),
        "next_step":            (
            "POST /api/claude/dispatch with {sensitive:true, task_id} "
            "to execute after review"
            if result.get("status") == "preview_pending" else None
        ),
        "error": result.get("error"),
    }, http_status)


@bp.route("/openclaw/status/<task_id>", methods=["GET"])
@require_auth
def get_status(task_id: str):
    """
    Poll task status. Returns compact audit view.
    Works for any task_id regardless of orchestration_source.
    """
    from engines.claude_dispatch import get_task as _get_task
    result = _get_task(task_id)
    if result is None:
        return _err("task not found", 404)
    return _ok(result)
