# AshbelOS Copilot Instructions

> Adapter of `docs/ashbelos-governance.md` and `docs/ashbelos-token-efficiency-policy.md`.
> Source of truth for governance and token policy lives in `docs/`. If conflict exists, `docs/` wins.

## Product Identity
- AshbelOS is the independent business core. OpenClaw is a detachable orchestration layer, not the core.
- Claude bridge is an orchestration interface only — business logic stays in AshbelOS engines.

## Stack
- Backend: Flask + Gunicorn (Python 3.11), Railway, PostgreSQL
- Phase 11 scoring: engines/phase11_engine.py (source of truth)
- Docs: docs/AGENT.md, docs/TELEGRAM.md, docs/FALLBACK.md, docs/INTEGRATIONS.md, docs/DEPLOY.md, docs/API.md

## Lead statuses (DB values, Hebrew)
- חדש, ניסיון קשר, מתעניין, סגור_זכה, סגור_הפסיד

## Phase 11 business states (scoring layer only)
- NEW_LEAD, QUOTE_SENT, AWAITING_MEASUREMENTS, AWAITING_APPROVAL, AWAITING_DEPOSIT, BLOCKED_CRITICAL

## Sensitive Action Flow
Intent → Preview → Approval → Execute → Audit Log
No sensitive action may skip Preview or Approval.

## Wave One External Channel
Telegram only. No other execution channels approved.

## Excluded from active scope
WhatsApp execution, Email, Calendar, remote file writes, new external connectors — do not introduce unless explicitly approved.

## Rules
- Token-efficient, one-pass execution
- Small steps; edit in place; prefer extension over new modules
- Do not relocate business memory, lead scoring, or revenue logic outside AshbelOS
- Do not refactor stable FSM logic
- Run pytest before commit
