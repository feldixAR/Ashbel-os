"""
mcp.py — Model Context Protocol (MCP) HTTP endpoint for ChatGPT.

Implements MCP Streamable HTTP transport (spec 2025-03-26).
Exposes one tool: get_latest_claude_task

POST /api/mcp  — JSON-RPC 2.0 handler (initialize, tools/list, tools/call)

Auth: X-API-Key header or Authorization: Bearer <key>
"""
import json
import logging
import os

from flask import Blueprint, request, jsonify

log = logging.getLogger(__name__)
bp  = Blueprint("mcp", __name__)

_TOOLS = [
    {
        "name": "get_latest_claude_task",
        "description": (
            "Returns the most recent Claude task from AshbelOS including "
            "task_id, intent (instruction), preview plan, execution status, "
            "Claude result summary, GPT review notes, and updated_at timestamp."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    }
]


def _auth_ok() -> bool:
    raw_env = os.getenv("OS_API_KEY", "").strip().strip('"').strip("'")
    client = (
        request.headers.get("X-API-Key", "")
        or request.headers.get("Authorization", "").removeprefix("Bearer ")
    ).strip()
    return bool(raw_env) and client == raw_env


def _rpc(req_id, result=None, error=None):
    body = {"jsonrpc": "2.0", "id": req_id}
    if error:
        body["error"] = error
    else:
        body["result"] = result
    return jsonify(body)


@bp.route("/mcp", methods=["POST"])
def mcp():
    body   = request.get_json(silent=True) or {}
    method = body.get("method", "")
    rid    = body.get("id")
    params = body.get("params") or {}

    # initialize — no auth required (handshake)
    if method == "initialize":
        return _rpc(rid, {
            "protocolVersion": "2025-03-26",
            "capabilities":    {"tools": {}},
            "serverInfo":      {"name": "AshbelOS", "version": "1.0.0"},
        })

    # notifications/initialized — ack, no response body needed
    if method == "notifications/initialized":
        return ("", 204)

    # all other methods require auth
    if not _auth_ok():
        return _rpc(rid, error={"code": -32001, "message": "unauthorized"}), 401

    if method == "tools/list":
        return _rpc(rid, {"tools": _TOOLS})

    if method == "tools/call":
        name = params.get("name")
        if name != "get_latest_claude_task":
            return _rpc(rid, error={"code": -32601, "message": f"unknown tool: {name}"})

        from services.storage.repositories.claude_task_repo import ClaudeTaskRepository
        task = ClaudeTaskRepository().get_latest()
        text = json.dumps(task.to_gpt_view(), ensure_ascii=False) if task else "no tasks found"
        return _rpc(rid, {"content": [{"type": "text", "text": text}]})

    return _rpc(rid, error={"code": -32601, "message": f"method not found: {method}"})
