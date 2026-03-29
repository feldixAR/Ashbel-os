# AshbelOS — Agent Context (CLAUDE.md)

> This file is the persistent memory for Claude Code agents working on this repo.
> Update the "Current Status" section at the end of every session.
> Do NOT re-read the Product Mission document on every turn — use this summary instead.

---

## Business Context — LOCKED

**This system operates exclusively for Ashbal Aluminum (אשבל אלומיניום).**
**Sector: Aluminum. No other business profile is active or permitted.**

| Field | Value |
|-------|-------|
| **Business** | אשבל אלומיניום — Ashbal Aluminum |
| **Sector** | Aluminum (`BUSINESS_ID=ashbel`, hardcoded default) |
| **Active Profile** | `ashbel` (see `config/business_registry.py`) |
| **Language** | Hebrew (he) |
| **Currency** | ILS |
| **Avg Deal Size** | ₪15,000 |

**Operating Rule: Do NOT add, restore, or reference any other business profile.**
**The `demo_real_estate` profile in `business_registry.py` is a scaffold — do not activate it.**

---

## Project Identity

| Field | Value |
|-------|-------|
| **Product** | AshbelOS — Autonomous Business Operating System |
| **Domain** | Ashbal Aluminum (אשבל אלומיניום) |
| **Runtime** | Flask + Gunicorn, PostgreSQL, Railway |
| **Language** | Python 3.11 |
| **Repo branch model** | `master` = production-ready; `fix/*` = hotfix branches |
| **Deploy target** | Railway (auto-deploys from `master` via GitHub push) |
| **Health endpoint** | `GET /api/health` → `{"status": "ok", "db": true}` |
| **Production URL** | `https://ashbel-os-production.up.railway.app` |

---

## Architecture (Do Not Repeat — Use This Summary)

```
WhatsApp / Dashboard UI
        ↓
  api/routes/*.py          (Flask Blueprints)
        ↓
  orchestration/orchestrator.py   (Intent → Task mapping)
        ↓
  orchestration/task_manager.py   (Task lifecycle: start → execute → complete/fail)
        ↓
  services/execution/executor.py  (Action dispatcher — _HANDLERS dict)
        ↓
  engines/*.py / agents/**        (Domain logic)
        ↓
  services/storage/               (PostgreSQL via SQLAlchemy)
```

### Key Contracts

- `OrchestratorResult` is a `@dataclass` — access `.message`, `.intent`, `.success` (not `.get("response")`)
- `orchestrator` (lowercase) = module-level singleton — never instantiate per-request
- `task_manager.dispatch()` owns full task lifecycle — orchestrator must NOT call `mark_completed/mark_failed`
- `_HANDLERS` in `executor.py` is a **module-level dict** defined AFTER all `_handle_*` functions

---

## Batch Inventory (Implemented)

| Batch | Feature Area | Status |
|-------|-------------|--------|
| 1 | CRM core (leads, tasks, orchestrator) | ✅ Implemented |
| 2 | Assistant / Draft flow | ✅ Implemented |
| 3 | Agent Factory | ✅ Implemented |
| 4 | Revenue Engine | ✅ Implemented |
| 5 | Event Bus + Scheduler | ✅ Implemented |
| 6 | Goal & Growth Engine | ✅ Implemented |
| 7 | Research & Asset Engine | ✅ Implemented |
| 8 | Outreach & Execution Engine | ✅ Implemented |
| 9 | Revenue Learning Engine | ✅ Implemented |

---

## Axis 1 — CLOSED ✅

**Proof:** `GET /api/health` → HTTP 200 `{"data":{"db":true,"status":"ok"},"success":true}` (verified 2026-03-26)
**Proof:** `POST /api/command {"command":"create_lead"}` → HTTP 200/201 with lead data (verified 2026-03-26)

### Fixes Applied

| Bug | File | Fix |
|-----|------|-----|
| NameError `_handle_set_goal` | `executor.py` | `_HANDLERS` moved to module-level AFTER all `_handle_*` functions (line 815) |
| BUG-1 lifecycle | `orchestrator.py` | `dispatch()` owns lifecycle — removed duplicate `mark_completed/mark_failed` |
| BUG-2 method name | `whatsapp.py` | Uses `orchestrator.handle_command()` + reads `result.message` |
| BUG-3 singleton | `whatsapp.py` | Module-level singleton imported — no per-request instantiation |
| DB schema drift | `db.py` | `_run_column_migrations()` runs `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` on startup |

---

## Axis 2 — CLOSED ✅

**Business alignment confirmed (2026-03-26):**
- Active profile: `ashbel` ✅
- Sector: aluminum ✅
- `dj` profile: removed ✅ (0 matches across all source files)
- `leads.sector` column: migration applied via `_run_column_migrations()` ✅

---

## Test Files

| File | Purpose | Status |
|------|---------|--------|
| `tests/test_executor_bootstrap.py` | AST-validates _HANDLERS structure + NameError fix | ✅ |
| `tests/test_runtime_flow_axis1.py` | AST-validates BUG-1, BUG-2, BUG-3 | ✅ |
| `tests/test_core_flow.py` | Intent parser + orchestrator + engine integration | ✅ |

---

## Environment Variables

| Variable | Source | Notes |
|----------|--------|-------|
| `DATABASE_URL` | Railway PostgreSQL add-on | Auto-injected by Railway |
| `OS_API_KEY` | Railway secret | Required for all API routes (`Ashbel2026`) |
| `SECRET_KEY` | Railway secret | Flask session key |
| `ANTHROPIC_API_KEY` | Railway secret | For AI-powered engines |
| `BUSINESS_ID` | Railway env | Set to `ashbel` (default if unset) |

---

## Operating Rules (for All Claude Agents)

1. **Business context is locked to Ashbal Aluminum.** Do not introduce or activate any other business profile.
2. **Use this file** for project context — do not re-read the entire codebase.
3. **Use git diffs** to verify changes, not full file re-reads.
4. **Bootstrap test must pass** before any Railway deploy is considered valid.
5. **Health check must return HTTP 200** with real proof, not assumption.
6. **Secrets never committed** — use `.env.example` as reference only.
7. **Axis 1 and Axis 2 are closed.** Do not reopen unless a new regression is proven with HTTP evidence.
