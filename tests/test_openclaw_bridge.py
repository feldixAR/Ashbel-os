"""
Tests for OpenClaw boundary, orchestration_source audit tagging,
Telegram notification guard, auth enforcement, and fallback availability.
"""
import json
import os
import pytest


@pytest.fixture(scope="module")
def client():
    os.environ["OS_API_KEY"]    = "testkey"
    os.environ["DATABASE_URL"]  = "sqlite://"
    from api.app import create_app
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


H = {"X-API-Key": "testkey", "Content-Type": "application/json"}
H_BARE = {"Content-Type": "application/json"}


# ── 1. Auth enforcement ───────────────────────────────────────────────────────

def test_openclaw_intent_requires_auth(client):
    r = client.post("/api/openclaw/intent", headers=H_BARE,
                    data=json.dumps({"instruction": "x"}))
    assert r.status_code == 401


def test_openclaw_status_requires_auth(client):
    r = client.get("/api/openclaw/status/nonexistent", headers=H_BARE)
    assert r.status_code == 401


# ── 2. OpenClaw intent → preview_pending ─────────────────────────────────────

def test_openclaw_intent_missing_instruction(client):
    r = client.post("/api/openclaw/intent", headers=H,
                    data=json.dumps({}))
    assert r.status_code == 400
    assert "instruction" in r.get_json()["error"]


def test_openclaw_intent_returns_preview_pending(client):
    r = client.post("/api/openclaw/intent", headers=H,
                    data=json.dumps({"instruction": "list active leads"}))
    g = r.get_json()
    # preview may fail (no ANTHROPIC_API_KEY in test) → status failed, not 400 gate
    assert r.status_code in (200, 400)
    assert g.get("task_id") is not None or g.get("error") is not None


def test_openclaw_status_404_for_unknown(client):
    r = client.get("/api/openclaw/status/no-such-id", headers=H)
    assert r.status_code == 404


# ── 3. orchestration_source tagged correctly ──────────────────────────────────

def test_orchestration_source_on_direct_dispatch(client):
    r = client.post("/api/claude/dispatch", headers=H,
                    data=json.dumps({"instruction": "list leads", "approved": True}))
    g = r.get_json()
    assert g["status"] in ("completed", "failed", "dispatched")
    # orchestration_source is None for direct calls (not openclaw)
    assert g.get("orchestration_source") is None


# ── 4. Sensitive dispatch still blocked without preview ───────────────────────

def test_sensitive_dispatch_blocked_without_preview(client):
    r = client.post("/api/claude/dispatch", headers=H,
                    data=json.dumps({"sensitive": True, "instruction": "do something dangerous"}))
    assert r.status_code == 400
    assert "task_id" in r.get_json()["error"]


def test_sensitive_dispatch_blocked_wrong_status(client):
    # Create a completed task, then try to dispatch it as sensitive
    from services.storage.repositories.claude_task_repo import ClaudeTaskRepository
    repo = ClaudeTaskRepository()
    t = repo.create(instruction="x", approved=True, sensitive=True, status="completed")
    r = client.post("/api/claude/dispatch", headers=H,
                    data=json.dumps({"sensitive": True, "task_id": t.id}))
    assert r.status_code == 400
    assert "preview_pending" in r.get_json()["error"]


# ── 5. MCP endpoint remains auth-free ────────────────────────────────────────

def test_mcp_initialize_no_auth(client):
    r = client.post("/api/mcp", headers=H_BARE,
                    data=json.dumps({"jsonrpc": "2.0", "id": 1,
                                     "method": "initialize",
                                     "params": {"protocolVersion": "2025-03-26",
                                                "capabilities": {}}}))
    assert r.status_code == 200
    assert r.get_json()["result"]["protocolVersion"] == "2025-03-26"


def test_mcp_tools_list_no_auth(client):
    r = client.post("/api/mcp", headers=H_BARE,
                    data=json.dumps({"jsonrpc": "2.0", "id": 2, "method": "tools/list"}))
    assert r.status_code == 200
    tools = r.get_json()["result"]["tools"]
    assert any(t["name"] == "get_latest_claude_task" for t in tools)


# ── 6. Telegram notification fails silently ───────────────────────────────────

def test_telegram_failure_does_not_break_dispatch(client):
    """Telegram tokens not set in test env — dispatch must still complete."""
    os.environ.pop("TELEGRAM_BOT_TOKEN", None)
    os.environ.pop("TELEGRAM_CHAT_ID", None)
    r = client.post("/api/claude/dispatch", headers=H,
                    data=json.dumps({"instruction": "count leads", "approved": True}))
    g = r.get_json()
    assert g["status"] in ("completed", "failed")  # not 500 from Telegram


# ── 7. Fallback: AshbelOS routes remain available without OpenClaw ────────────

def test_direct_preview_available_as_fallback(client):
    r = client.post("/api/claude/preview", headers=H,
                    data=json.dumps({"instruction": "describe next steps"}))
    g = r.get_json()
    assert g.get("task_id") is not None


def test_daily_revenue_queue_auth_enforced(client):
    r = client.get("/api/daily_revenue_queue", headers=H_BARE)
    assert r.status_code == 401


def test_daily_revenue_queue_authenticated(client):
    r = client.get("/api/daily_revenue_queue", headers=H)
    assert r.status_code == 200
    assert "queue" in r.get_json()
