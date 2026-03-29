"""
gpt_connector.py — GPT review and redispatch connector.

Exposes four tools over AshbelOS API so GPT can read Claude results,
save review notes, and — with explicit user approval — redispatch
follow-up instructions through the existing sensitive flow.

Tools:
  GET  /api/gpt/latest_task                         → get_latest_claude_task
  GET  /api/gpt/tasks/<task_id>                     → get_claude_task
  POST /api/gpt/tasks/<task_id>/review              → save_review_notes
  POST /api/gpt/tasks/<task_id>/redispatch          → approve_review_and_redispatch

All reads return the stable compact GPT view:
  {task_id, intent, preview, status, claude_result, review_notes, updated_at}

redispatch enforces the full sensitive flow:
  preview (Claude plans) → dispatch (execute) → audit row persisted
"""
import logging
from flask import Blueprint, request, jsonify
from api.middleware import require_auth

_OPENAPI_SPEC = {
  "openapi": "3.1.0",
  "info": {"title": "AshbelOS GPT Connector", "version": "1.0.0"},
  "servers": [{"url": "https://ashbel-os-production.up.railway.app"}],
  "paths": {
    "/api/gpt/latest_task": {
      "get": {
        "operationId": "get_latest_claude_task",
        "summary": "Get the most recent Claude task",
        "security": [{"ApiKeyAuth": []}],
        "responses": {"200": {"description": "Latest task"}}
      }
    },
    "/api/gpt/tasks/{task_id}": {
      "get": {
        "operationId": "get_claude_task",
        "summary": "Get a Claude task by ID",
        "security": [{"ApiKeyAuth": []}],
        "parameters": [{"name": "task_id", "in": "path", "required": True, "schema": {"type": "string"}}],
        "responses": {"200": {"description": "Task"}}
      }
    },
    "/api/gpt/tasks/{task_id}/review": {
      "post": {
        "operationId": "save_review_notes",
        "summary": "Save GPT review notes for a Claude task",
        "security": [{"ApiKeyAuth": []}],
        "parameters": [{"name": "task_id", "in": "path", "required": True, "schema": {"type": "string"}}],
        "requestBody": {
          "required": True,
          "content": {"application/json": {"schema": {
            "type": "object",
            "required": ["notes"],
            "properties": {"notes": {"type": "string"}}
          }}}
        },
        "responses": {"200": {"description": "Updated task"}}
      }
    },
    "/api/gpt/tasks/{task_id}/redispatch": {
      "post": {
        "operationId": "approve_review_and_redispatch",
        "summary": "Approve review and redispatch a follow-up instruction to Claude",
        "security": [{"ApiKeyAuth": []}],
        "parameters": [{"name": "task_id", "in": "path", "required": True, "schema": {"type": "string"}}],
        "requestBody": {
          "required": True,
          "content": {"application/json": {"schema": {
            "type": "object",
            "required": ["approved_instruction"],
            "properties": {"approved_instruction": {"type": "string"}}
          }}}
        },
        "responses": {"200": {"description": "Follow-up task result"}}
      }
    }
  },
  "components": {
    "securitySchemes": {
      "ApiKeyAuth": {"type": "apiKey", "in": "header", "name": "X-API-Key"}
    }
  }
}

log = logging.getLogger(__name__)
bp  = Blueprint("gpt_connector", __name__)


def _ok(data: dict, status: int = 200):
    return jsonify({"success": True, **data}), status


def _err(message: str, status: int = 400):
    return jsonify({"success": False, "error": message}), status


# ── GET /api/gpt/openapi.json (ChatGPT Actions schema) ───────────────────────

@bp.route("/gpt/openapi.json", methods=["GET"])
def openapi_schema():
    return jsonify(_OPENAPI_SPEC)


# ── GET /api/gpt/latest_task ──────────────────────────────────────────────────

@bp.route("/gpt/latest_task", methods=["GET"])
@require_auth
def get_latest_claude_task():
    from services.storage.repositories.claude_task_repo import ClaudeTaskRepository
    task = ClaudeTaskRepository().get_latest()
    if task is None:
        return _err("no tasks found", 404)
    return _ok(task.to_gpt_view())


# ── GET /api/gpt/tasks/<task_id> ──────────────────────────────────────────────

@bp.route("/gpt/tasks/<task_id>", methods=["GET"])
@require_auth
def get_claude_task(task_id: str):
    from services.storage.repositories.claude_task_repo import ClaudeTaskRepository
    task = ClaudeTaskRepository().get(task_id)
    if task is None:
        return _err("task not found", 404)
    return _ok(task.to_gpt_view())


# ── POST /api/gpt/tasks/<task_id>/review ─────────────────────────────────────

@bp.route("/gpt/tasks/<task_id>/review", methods=["POST"])
@require_auth
def save_review_notes(task_id: str):
    body = request.get_json(silent=True) or {}
    notes = (body.get("notes") or "").strip()
    if not notes:
        return _err("notes is required", 400)

    from services.storage.repositories.claude_task_repo import ClaudeTaskRepository
    repo = ClaudeTaskRepository()
    task = repo.get(task_id)
    if task is None:
        return _err("task not found", 404)

    repo.update(task_id, review_notes=notes)
    task = repo.get(task_id)
    log.info(f"[GPT] review notes saved for task {task_id[:8]}")
    return _ok(task.to_gpt_view())


# ── POST /api/gpt/tasks/<task_id>/redispatch ──────────────────────────────────

@bp.route("/gpt/tasks/<task_id>/redispatch", methods=["POST"])
@require_auth
def approve_review_and_redispatch(task_id: str):
    """
    Requires:
      - existing task with saved review_notes (enforces prior review step)
      - approved_instruction in body (the follow-up instruction to send to Claude)

    Flow enforced:
      1. Validates prior task exists and has review_notes
      2. Calls preview() → creates a new preview_pending sensitive task
      3. Dispatches that task via the sensitive path (task_id → execute)
      4. Returns the completed follow-up task (full audit trail in DB)
    """
    body = request.get_json(silent=True) or {}
    approved_instruction = (body.get("approved_instruction") or "").strip()
    if not approved_instruction:
        return _err("approved_instruction is required", 400)

    from services.storage.repositories.claude_task_repo import ClaudeTaskRepository
    repo = ClaudeTaskRepository()
    origin = repo.get(task_id)
    if origin is None:
        return _err("origin task not found", 404)
    if not origin.review_notes:
        return _err("review notes must be saved before redispatch", 400)

    from engines.claude_dispatch import preview as _preview, dispatch as _dispatch

    # Step 1: preview — Claude plans the follow-up
    preview_result = _preview({
        "instruction":  approved_instruction,
        "repo":         origin.repo,
        "branch":       origin.branch,
        "allowed_paths": origin.allowed_paths,
    })

    if preview_result["status"] == "failed":
        return _err(f"preview failed: {preview_result.get('error')}", 500)

    new_task_id = preview_result["task_id"]

    # Step 2: dispatch — explicit approval is the act of calling this endpoint
    dispatch_result = _dispatch({
        "sensitive": True,
        "task_id":   new_task_id,
    })

    log.info(f"[GPT] redispatch complete: origin={task_id[:8]} follow_up={new_task_id[:8]} status={dispatch_result['status']}")

    return _ok({
        "origin_task_id":  task_id,
        "follow_up":       dispatch_result,
    }, 200 if dispatch_result["status"] in ("completed", "dispatched") else 500)
