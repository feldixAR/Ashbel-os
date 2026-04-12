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
| 10 | Mobile Quick Actions / Voice / Fast Access / Admin Layer | ✅ Implemented |
| 11 | Revenue Queue Scoring Engine (`GET /api/daily_revenue_queue`) | ✅ Implemented |
| 12 | Lead Acquisition OS — 6 skill modules, acquisition engine, 7 API endpoints, light UI, 5 new event hooks | ✅ Implemented |
| 13 | LeadAcquisitionAgent — registry-owned, Haiku batch signal filter, Sonnet inbound draft, scheduled follow-up proposals | ✅ Implemented |
| 14 | Brief/batch-score/execute endpoints — AI lead briefing, batch Haiku scoring, approval execute flow + activity log | ✅ Implemented |
| Bridge | Claude Dispatch (`POST /api/claude/preview`, `/dispatch`, `/tasks/<id>`) — sensitive flow enforced | ✅ Implemented |
| Bridge | GPT Connector (`/api/gpt/*`) — review, redispatch, OpenAPI schema | ✅ Implemented |
| Bridge | MCP Endpoint (`POST /api/mcp`) — ChatGPT-compatible, no-auth, `get_latest_claude_task` | ✅ Implemented |
| Channel | Telegram Inbound Webhook (`POST /api/telegram/webhook`) — Wave One approved, orchestrator dispatch | ✅ Implemented |

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
| `TELEGRAM_BOT_TOKEN` | Railway secret | Telegram Bot API token from @BotFather |
| `TELEGRAM_CHAT_ID` | Railway secret | Target chat/channel ID for outbound messages |
| `WEBHOOK_VERIFY_TOKEN` | Railway secret | Authenticates inbound Telegram webhook |
| `WHATSAPP_ACCESS_TOKEN` | Railway secret | Meta WhatsApp Business API access token |
| `WHATSAPP_PHONE_NUMBER_ID` | Railway secret | Meta WhatsApp sender phone number ID |
| `GMAIL_CREDENTIALS_JSON` | Railway secret | Google service account JSON for Gmail listener |
| `GOOGLE_MAPS_API_KEY` | Railway secret | Google Maps Places API key for lead scraper |

---

## Operating Rules (for All Claude Agents)

1. **Business context is locked to Ashbal Aluminum.** Do not introduce or activate any other business profile.
2. **Use this file** for project context — do not re-read the entire codebase.
3. **Use git diffs** to verify changes, not full file re-reads.
4. **Bootstrap test must pass** before any Railway deploy is considered valid.
5. **Health check must return HTTP 200** with real proof, not assumption.
6. **Secrets never committed** — use `.env.example` as reference only.
7. **Axis 1 and Axis 2 are closed.** Do not reopen unless a new regression is proven with HTTP evidence.
8. **Work in small steps only.** Edit existing modules in place; prefer extension over parallel systems.
9. **Before sensitive implementation:** preview must be clear and approval explicit.

---

## Governance Policy

> Source of truth: `docs/ashbelos-governance.md` (repo-resident). This section is its adapter. If conflict exists, the source-of-truth doc wins until this section is corrected.

### Product Layers
- **AshbelOS** is the independent business core. Its autonomy must not be weakened.
- **OpenClaw** is a detachable orchestration/control layer. It orchestrates AshbelOS; it does not replace it.
- The Claude bridge (`engines/claude_dispatch.py`, `api/routes/claude_dispatch.py`) is an orchestration interface only — not business core.

### Sensitive Action Flow (mandatory)
```
Intent → Preview → Approval → Execute → Audit Log
```
No sensitive action may skip Preview or Approval.

### Business Logic Residency (must stay native to AshbelOS)
- Business memory
- Lead scoring
- Revenue logic
- Israeli business adaptation
- Critical execution fallback paths

These may be orchestrated externally but must not be relocated as source of truth.

### Fallback Policy
Critical execution paths must support AshbelOS-native fallback. If any external bridge or orchestration layer fails, core business execution must remain possible through AshbelOS directly.

### Wave One External Channels
**Approved:** Telegram only.

### Excluded from Active Approved Scope
Do not introduce the following unless explicitly approved:
- WhatsApp execution (route exists; do not expand)
- Email execution
- Calendar execution
- Remote file writes
- Additional external connectors
- New infrastructure not required by the current approved phase

---

## Token Discipline Policy

> Source of truth: `docs/ashbelos-token-efficiency-policy.md` (repo-resident). This section is its adapter.

This policy is binding for all work in this repository.

### Core rule

Always optimize for maximum token efficiency without reducing code quality, correctness, safety, or implementation clarity.

### Required behavior

* Stay in execution mode once scope is approved.
* Start from current repo state only.
* Do not restart broad analysis unless a true blocker requires it.
* Do not recap old context that is already established.
* Do not reopen closed architecture decisions.
* Do not ask for confirmation for normal repo work.
* Do not create parallel systems when existing modules can be extended.
* Prefer direct implementation over long investigation.

### Repo reading discipline

* Read only files required for the current task or phase.
* Do not rescan the whole repo unless strictly necessary.
* Do not reread files that were already verified unless they changed or are directly relevant.
* Prefer targeted inspection over broad exploration.

### Tool and agent discipline

* Do not launch broad subagents unless strictly necessary.
* Use the smallest effective tool/action path.
* Avoid repeated scans, repeated status checks, and repeated summaries.
* Prefer one focused pass over multiple exploratory passes.

### Output discipline

* Return compact status only unless more detail is explicitly requested.
* Keep updates short and execution-first.
* Mark completed checklist items with [x].
* Report only what changed, what is in progress, and true blockers.

### Scope discipline

* Work in controlled phases.
* Complete the current approved phase before expanding scope.
* Do not mix unrelated batches in one run unless explicitly requested.
* Stop only for:

  * true external blockers
  * missing credentials
  * destructive risk
  * deployment/runtime actions outside the repo

### Architectural discipline

* Preserve approved business logic, sensitive flow, auditability, fallback behavior, and AshbelOS as the independent business core.
* No token-saving shortcut may weaken architecture or correctness.

### Priority order

1. Safety and correctness
2. Approved architecture and policy compliance
3. Token efficiency
4. Execution speed
5. Extra explanation

---

## Session Updates — Phase 17: Mission Control + Learning + Self-Evolution v5.1

- **Date:** 2026-04-12
- **Phases complete:** 3–17 + UI + SEO
- **Test count:** 246 passing (all green)
- **Phase 12 new components:**
  - `skills/` package: `source_discovery`, `lead_intelligence`, `outreach_intelligence`, `israeli_context`, `workflow_skills`, `website_growth` — all stateless, contract-based, multi-agent compatible
  - `engines/lead_acquisition_engine.py` — orchestrating pipeline (goal → plan → normalize → dedup → enrich → score → outreach → CRM → events)
  - `api/routes/lead_ops.py` — 7 endpoints: discover, inbound, website, queue, plan, draft, status
  - `events/event_types.py` — 5 new event constants: LEAD_DISCOVERED, INBOUND_LEAD_RECEIVED, LEAD_OUTREACH_SENT, LEAD_FOLLOWUP_PROPOSED, WEBSITE_ANALYSIS_REQUESTED
  - `events/handlers/lead_acquisition_handlers.py` — 5 handlers wired in dispatcher
  - `services/storage/models/lead_discovery.py` — discovery session model
  - Lead model: +9 acquisition columns (source_type, segment, outreach_action, outreach_draft, is_inbound, …)
  - `orchestration/intent_parser.py` — 4 new intents: DISCOVER_LEADS, PROCESS_INBOUND, WEBSITE_ANALYSIS, LEAD_OPS_QUEUE
  - `ui/css/app.css` — light theme (token swap only)
  - `ui/js/panels/lead_ops.js` — full lead ops surface (tabs: inbound/discovered/pending/meetings, discover modal, website analysis modal)
- **Phase 13 additions:**
  - `agents/departments/sales/lead_acquisition_agent.py` — registered in registry, handles all acquisition/* actions
  - Haiku batch signal pre-classification (call_batch), Sonnet inbound draft with prompt cache
  - Local-first: empty signals → plan only (0 tokens)
  - `scheduler/revenue_scheduler.py` — `_job_lead_followup_proposals()` daily 09:00 IL
- **Phase 14 additions:**
  - `GET /api/lead_ops/brief/<id>` — AI lead briefing (Haiku + deterministic fallback)
  - `POST /api/lead_ops/batch_score` — deterministic scoring + Haiku explanations for top 5
  - `POST /api/lead_ops/execute/<id>` — approval execute flow: approve/deny, ActivityModel log, LEAD_OUTREACH_SENT event
- **Governance:** all outreach drafts require_approval=True; no unapproved execution channels opened; sensitive flow enforced
- **Phase 15 additions:**
  - `events/handlers/lead_acquisition_handlers.py` — Telegram hot-lead alerts (score≥70) and inbound approval cards
  - `api/routes/approvals.py` — `_resolve_approval()` closes lead-ops loop: ActivityModel log + LEAD_OUTREACH_SENT event
- **Phase 16 additions:**
  - `services/intake/normalizer.py` — unified channel-agnostic normalizer for all Telegram payload types → IntakePayload
  - `skills/document_intelligence.py` — stateless document parser: CSV/Excel/Word/PDF/TXT, Hebrew+English column detection
  - `api/routes/telegram.py` — full multi-modal routing via normalize_telegram(); document download → task_manager dispatch; voice fallback; contact → process_inbound
  - `services/execution/executor.py` — `_handle_parse_document` (base64 → parse → process_inbound per record); `_handle_preview_system_change` (classify → preview → ApprovalModel → Telegram card)
  - `orchestration/intent_parser.py` — DOCUMENT_UPLOAD + SYSTEM_CHANGE intents
  - `orchestration/orchestrator.py` — DOCUMENT_UPLOAD → acquisition/parse_document; SYSTEM_CHANGE → executive/preview_system_change
- **Phase 17 additions:**
  - `ui/js/panels/revenue.js` — Mission Control: State→Recommendation→Action added
    `revInsight` (deals/hot leads/pipeline chips) + `revNextAction` (top priority item button)
  - `skills/learning_skills.py` — stateless pattern tracking via MemoryStore
    template outcome/promotion, source strategy (3-run qualification threshold),
    agent success/latency tracking, lead conversion by score bucket, model routing overrides
  - `api/routes/approvals.py` — system_change approval: auto-creates `feat/system-change-{id}` branch,
    stores execution plan in MemoryStore `global.pending_change_{id}` for implementation pass
  - `tests/test_learning_skills.py` — 21 unit tests for learning_skills (fake MemoryStore, no DB)
- **Status: PRODUCTION READY v5.1**

---

## Continuous Development Mode

- Work from current repo reality only.
- Do not re-derive architecture, flows, or decisions already established in code, docs, or commits.
- Do not rescan the full repo unless required by a real change.
- Read only files relevant to the current step.
- Prefer metadata-first inspection before deep reads.
- Prefer extending existing components over creating new systems.
- Keep outputs checkpoint-based and compact.
- Continue execution without stopping for minor confirmations.
- Stop only for real architectural, policy, or runtime blockers.
- Completion requires runtime proof, not code structure alone.

---

## Safe Self-Modification Rule

- Any request to change system behavior, UI, modules, flows, or docs is a sensitive action.
- Sensitive changes must follow: Intent → Preview → Approval → Branch/PR → Verification → Deploy
- Never mutate production behavior or core flows without explicit approval.
- Always preserve a rollback path via Git and deploy history.
- Detect and report conflicts before applying system changes.

---

## External Capability Intake Rules

- Do not clone or import large external repositories by default.
- Use metadata and documentation before loading full implementations.
- External skills, agents, MCPs are capabilities only, not source of truth.
- AshbelOS remains source of truth for state, DB, lifecycle, approvals, and audit.
- Prefer lightweight adapters over full-code imports.
- Before using external capability, record: source, purpose, scope, trust level, approval sensitivity, integration point.
- Reuse existing internal logic before adding external capability.
