# AshbelOS — Agent Context (CLAUDE.md)

> This file is the persistent memory for Claude Code agents working on this repo.
> Update the "Current Status" section at the end of every session.
> Do NOT re-read the Product Mission document on every turn — use this summary instead.

---

## Project Identity

| Field | Value |
|-------|-------|
| **Product** | AshbelOS — Autonomous Business Operating System |
| **Domain** | Ashbal Aluminum (אשבל אלומיניום) |
| **Runtime** | FastAPI/Flask + Gunicorn, PostgreSQL, Railway |
| **Language** | Python 3.11 |
| **Repo branch model** | `main` = production-ready; `fix/*` = hotfix branches |
| **Deploy target** | Railway (auto-deploys from `main` via GitHub push) |
| **Health endpoint** | `GET /api/health` → `{"status": "ok"}` |

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

**Current Priority: Stabilization only. No new batch development until Axis 1 is closed.**

---

## Axis 1 Stabilization — Status

### The Bug (Root Cause)
```
NameError: name '_handle_set_goal' is not defined
```
**Root cause:** In the original codebase, `_HANDLERS` (or the equivalent handler registry) was
defined as a module-level dict BEFORE the `_handle_set_goal` function was defined, or wrapped
inside `_get_handlers()` in a way that caused a forward-reference failure on import.

### The Fix Applied
**File:** `services/execution/executor.py`

- ❌ **Before:** `_get_handlers()` function returned the dict (lazy wrapper, caused test failures)
- ✅ **After:** `_HANDLERS: Dict[str, Callable] = { ... }` defined at **module level, line 816**,
  AFTER all `_handle_*` functions (last handler defined at line ~807).
- `execute()` now uses `_HANDLERS.get(action)` directly.

**Structural proof (grep-validated):**
```
518: def _handle_set_goal(...)       ← function defined
816: _HANDLERS: Dict[str, Callable] = {  ← dict assigned AFTER function
841:   "set_goal": _handle_set_goal,  ← reference is valid
882: handler = _HANDLERS.get(action)  ← execute() uses dict directly
```

### BUG-1 (orchestrator.py) — FIXED
`handle_command()` no longer calls `mark_completed/mark_failed` — `dispatch()` owns lifecycle.

### BUG-2 (whatsapp.py) — FIXED
`receive_webhook()` calls `orchestrator.handle_command(text)` and reads `result.message`.

### BUG-3 (whatsapp.py) — FIXED
Module-level singleton `orchestrator` imported — no per-request instantiation.

---

## Test Files

| File | Purpose | Status |
|------|---------|--------|
| `tests/test_executor_bootstrap.py` | AST-validates _HANDLERS structure + NameError fix | ✅ Created |
| `tests/test_runtime_flow_axis1.py` | AST-validates BUG-1, BUG-2, BUG-3 | ✅ Exists |
| `tests/test_core_flow.py` | Intent parser + orchestrator + engine integration | ✅ Exists |

---

## GitHub Workflow

**File:** `.github/workflows/fix-bootstrap.yml`
**Trigger:** `workflow_dispatch` (manual)

**Sequence:**
1. Checkout `fix/axis1-runtime-flow`
2. Run `tests/test_executor_bootstrap.py`
3. Run `tests/test_runtime_flow_axis1.py`
4. Merge → `main`
5. Trigger Railway deploy via `secrets.RAILWAY_TOKEN`
6. Wait 60s
7. Health check `secrets.RAILWAY_URL/api/health`

---

## Git State (as of 2026-03-26)

```
Branch: fix/axis1-runtime-flow  (= main, fix already committed)
Commits:
  98080b1 chore: initial commit — full AshbelOS codebase from zip
           [includes executor.py fix + test_executor_bootstrap.py]
```

**Remote:** NOT configured yet — push blocked pending GitHub repo URL.

---

## Environment Variables Required

| Variable | Source | Notes |
|----------|--------|-------|
| `DATABASE_URL` | Railway PostgreSQL add-on | Auto-injected by Railway |
| `API_KEY` | Railway secret | Required for all API routes |
| `SECRET_KEY` | Railway secret | Flask session key |
| `ANTHROPIC_API_KEY` | Railway secret | For AI-powered engines |
| `RAILWAY_TOKEN` | GitHub secret | For CI deploy trigger |
| `RAILWAY_URL` | GitHub secret | e.g. `https://ashbelos.up.railway.app` |

---

## Current Axis 1 Closure Checklist

- [x] `executor.py` fix applied and validated locally
- [x] `tests/test_executor_bootstrap.py` created
- [x] `fix/axis1-runtime-flow` branch exists with fix committed
- [ ] **BLOCKED: GitHub remote not configured** — need repo URL + push access
- [ ] GitHub push → `fix/axis1-runtime-flow`
- [ ] Trigger `fix-bootstrap.yml` workflow manually (Actions tab)
- [ ] Confirm Railway deploy completes (check Railway dashboard)
- [ ] Confirm `GET /api/health` returns HTTP 200 with `{"status": "ok"}`
- [ ] Axis 1 closed with real production proof

---

## Operating Rules (for All Claude Agents)

1. **Never start a new batch** until Axis 1 checklist above is 100% complete with proof.
2. **Use this file** for project context — do not re-read the entire codebase.
3. **Use git diffs** to verify changes, not full file re-reads.
4. **Bootstrap test must pass** before any Railway deploy is considered valid.
5. **Health check must return HTTP 200** with real log proof, not assumption.
6. **Secrets never committed** — use `.env.example` as reference only.
