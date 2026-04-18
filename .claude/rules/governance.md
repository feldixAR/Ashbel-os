# AshbelOS — Governance Enforcement Rules

> These rules enforce existing policy from `docs/ashbelos-governance.md` and
> `docs/ashbelos-token-efficiency-policy.md`. No new policy is introduced here.
> Source of truth order: CLAUDE.md → docs/ashbelos-governance.md → this file.

---

## Business Context (Locked)

- Active business: **Ashbal Aluminum (אשבל אלומיניום)** only
- `BUSINESS_ID=ashbel` — hardcoded default, never change
- Do NOT activate `demo_real_estate` or any other business profile
- All UI, copy, and logic must be Hebrew / ILS / aluminum sector

---

## Sensitive Action Flow (Mandatory)

Every sensitive action must follow this exact sequence — no shortcuts:

```
Intent → Preview → Approval → Execute → Audit Log
```

- All outreach drafts: `requires_approval: True`
- No execution without an `ApprovalModel` record
- ActivityModel log entry required on every resolution
- `LEAD_OUTREACH_SENT` event emitted on approval

---

## External Channels (Wave One)

- **Approved:** Telegram only
- **Not approved:** WhatsApp execution, Email, Calendar, remote file writes, new external connectors
- WhatsApp route exists — do not expand it

---

## Business Logic Residency

Must stay native to AshbelOS — never relocate:
- Business memory
- Lead scoring
- Revenue logic
- Israeli business adaptation
- Critical execution fallback paths

These may be orchestrated externally but AshbelOS is always source of truth.

---

## Fallback Policy

Critical execution paths must support AshbelOS-native fallback.
If any external bridge (Claude, GPT, MCP) fails, core business execution must remain possible directly.

---

## Architecture Constraints

- `orchestrator` = module-level singleton — never instantiate per-request
- `task_manager.dispatch()` owns full task lifecycle — orchestrator must NOT call mark_completed/mark_failed
- `_HANDLERS` in `executor.py` must be defined AFTER all `_handle_*` functions
- `OrchestratorResult` is a `@dataclass` — access `.message`, `.intent`, `.success`

---

## Token Discipline

- Local-first: check `_local_compute()` before any AI call
- Model routing: Haiku → classify/route, Sonnet → draft/content, Opus → strategy
- Do not restart broad analysis; prefer targeted inspection
- Read only files required for current task

---

## Commit Gate

- Run `PYTHONPATH=. python -m pytest tests/ -q` before every commit — all must pass
- Never commit secrets (`.env`, credentials)
- CLAUDE.md must be updated at end of every session with current status

---

## Safe Self-Modification

- Any change to system behavior, UI, modules, flows, or docs is a sensitive action
- Must follow: Intent → Preview → Approval → Branch/PR → Verification → Deploy
- Never mutate production behavior without explicit approval
- Always preserve a rollback path via Git and deploy history
