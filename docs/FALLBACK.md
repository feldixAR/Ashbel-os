# AshbelOS Fallback and Failure Modes

> Governance source: `docs/ashbelos-governance.md` §Fallback Policy

---

## Principle

If any external bridge or orchestration layer fails, core business execution must remain possible through AshbelOS directly.

---

## Failure Scenarios and Fallback Behavior

### 1. Anthropic API Unavailable

| Layer affected | Fallback |
|----------------|---------|
| All agents using `_ai_call()` | `_local_compute()` runs first and may return a result without any AI call |
| ChiefOfStaffAgent | Returns local timing/quota check result |
| LeadQualifierAgent | Returns score from deterministic `compute_score()` in `lead_engine.py` |
| MessagingAgent | No local fallback — returns error, outreach is blocked |
| SEOEngine | No AI dependency — fully deterministic, unaffected |

**Code guarantee:** `BaseAgent._ai_call()` catches all exceptions and returns `ExecutionResult(success=False, ...)`. Orchestrator handles gracefully via `task_manager`.

---

### 2. Telegram Service Unavailable

| Scenario | Behavior |
|----------|---------|
| `telegram_service.send()` fails | Exception caught, logged via `StructuredLogger`, not re-raised |
| Inbound webhook fails auth | Returns HTTP 401 — no orchestrator call made |
| Approval callback fails | `answer_callback()` catches exception; approval state not affected |

**Important:** Telegram failure does not block core CRM or outreach logic. The approval flow can be resolved via `POST /api/approvals/{id}` from the Dashboard UI directly.

---

### 3. PostgreSQL Unavailable

| Scenario | Behavior |
|----------|---------|
| `GET /api/health` | Returns `{"db": false}` — Railway will restart the pod |
| Any route requiring DB | Returns HTTP 500 with error message — no silent data loss |
| `_run_column_migrations()` at startup | Logs error but does not crash app startup on transient failure |

---

### 4. External Bridge Failure (OpenClaw / GPT Connector / MCP)

| Bridge | Fallback |
|--------|---------|
| OpenClaw unavailable | `POST /api/command` continues to work — orchestrator is independent |
| GPT Connector (`/api/gpt/*`) fails | Core CRM unaffected — bridge routes are additive only |
| MCP endpoint (`/api/mcp`) fails | Core CRM unaffected — MCP is read-only (`get_latest_claude_task`) |
| Claude bridge (`/api/claude/*`) fails | Core unaffected — bridge is orchestration interface only |

---

### 5. Gmail Listener / Lead Scraper Unavailable

Both services use stub mode. If credentials are missing:

```python
# gmail_listener.py
if not os.getenv("GMAIL_CREDENTIALS_JSON"):
    return []  # silent stub

# lead_scraper.py
if not os.getenv("GOOGLE_MAPS_API_KEY"):
    return []  # silent stub
```

Scheduler jobs continue running but produce no leads. No exception is raised. Telegram notification is skipped.

---

## Audit Trail Integrity

The sensitive action flow writes an audit record at the Approval step. If `execute_outreach()` fails after approval:
- Approval record is already committed to DB with `action=approve`
- Failure is logged via `StructuredLogger` (ERROR level → Telegram alert)
- The approval is not re-triggered automatically — operator must re-initiate

---

## Health Check

`GET /api/health` is the single canonical liveness signal.

```json
{"data": {"db": true, "status": "ok"}, "success": true}
```

Railway uses this as the healthcheck path (see `railway.json`). If it returns non-200 or `db: false`, Railway restarts the pod.
