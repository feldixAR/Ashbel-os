# AshbelOS Copilot Instructions

> Adapter of `docs/ashbelos-governance.md` and `docs/ashbelos-token-efficiency-policy.md`.
> Source of truth priority: CLAUDE.md → docs/ashbelos-governance.md → docs/ashbelos-token-efficiency-policy.md → this file.
> If conflict exists, `docs/` wins. This file is always behind CLAUDE.md.

## Product Identity
- **Version:** v5.2 — Guided Operator Console (Phase 21 complete)
- AshbelOS is the independent business core. OpenClaw is a detachable orchestration layer, not the core.
- Claude bridge (`engines/claude_dispatch.py`, `api/routes/claude_dispatch.py`) is an orchestration interface only — business logic stays in AshbelOS engines.
- Business: אשבל אלומיניום (Ashbal Aluminum) — aluminum windows, doors, pergolas. Israeli market. ILS. Hebrew UI.

## Stack
- Backend: Flask + Gunicorn (Python 3.11), Railway, PostgreSQL
- Auth: `X-API-Key` header (`OS_API_KEY`) on all routes except health/webhook/mcp
- Phase 11 revenue queue scoring: `engines/phase11_engine.py` (source of truth for scoring)
- Skills: `skills/` — stateless, contract-based, no DB
- Docs: `docs/AGENT.md`, `docs/TELEGRAM.md`, `docs/FALLBACK.md`, `docs/INTEGRATIONS.md`, `docs/DEPLOY.md`, `docs/API.md`, `docs/AGENTS_SKILLS_ORCHESTRATION.md`, `docs/PRODUCT_OPERATING_MODEL.md`, `docs/UI_UX_MOBILE_RULES.md`, `docs/DEPLOY_AND_VERIFICATION_DISCIPLINE.md`

## Implemented Phases (all ✅)
- Phases 1–10: CRM, Revenue, Outreach, Mobile, Admin, Token optimization, Policy, Observability, SEO
- Phase 12: Lead Acquisition OS — 6 skill modules, acquisition engine, 7 API endpoints
- Phase 13: LeadAcquisitionAgent — Haiku batch signal filter, Sonnet inbound draft, local-first
- Phase 14: Brief/batch-score/execute endpoints + approval execute flow + ActivityModel log
- Phase 15: Telegram hot-lead alerts (score≥70) + inbound approval cards
- Phase 16: Channel-native intake normalizer + document intelligence (CSV/Excel/Word/PDF) + self-evolution branch flow
- Phase 17: Mission Control UI (revenue/calendar/pipeline/goals/seo) + learning skills + self-evolution branch creation
- Phase 18: Home panel, upload/intake modal, CSS UX completion
- Phase 19: Mobile sidebar toggle, real discovery, overlay modal, mobile cards
- Phase 20: pytz fallback system-wide + guided UX pass (guided empty states, CTAs)
- Phase 21: Guided operator console — DraftModal component, per-row Draft+Briefing actions, `POST /api/approvals/create`

## Lead Statuses (DB values, Hebrew)
- חדש, ניסיון קשר, מתעניין, סגור_זכה, סגור_הפסיד

## Phase 11 Business States (scoring layer only)
- NEW_LEAD, QUOTE_SENT, AWAITING_MEASUREMENTS, AWAITING_APPROVAL, AWAITING_DEPOSIT, BLOCKED_CRITICAL

## Sensitive Action Flow (mandatory — no exceptions)
```
Intent → Preview → Approval → Execute → Audit Log
```
No sensitive action may skip Preview or Approval. All outreach drafts: `requires_approval: True`.

## Wave One External Channel
Telegram only. No other execution channels approved.

## Excluded from Active Scope
WhatsApp execution, Email, Calendar, remote file writes, new external connectors — do not introduce unless explicitly approved.

## Key Contracts
- `OrchestratorResult` is a `@dataclass` — use `.message`, `.intent`, `.success`
- `orchestrator` = module-level singleton — never instantiate per-request
- `task_manager.dispatch()` owns full task lifecycle — orchestrator must NOT call mark_completed/mark_failed
- `_HANDLERS` defined AFTER all `_handle_*` functions in `executor.py`

## Rules
- Token-efficient, one-pass execution
- Small steps; edit in place; prefer extension over new modules
- Do not relocate business memory, lead scoring, or revenue logic outside AshbelOS
- Do not refactor stable FSM or scoring logic
- Run pytest (246 tests) before commit — all must pass
- Never commit secrets
- CLAUDE.md is primary truth — update it at end of every session
