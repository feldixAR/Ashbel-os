# AshbelOS Governance Document

> **Source of truth for all governance decisions.**
> CLAUDE.md §Governance Policy is an adapter of this document. If conflict exists, this document wins until CLAUDE.md is corrected.

---

## Product Layers

**AshbelOS** is the independent business core. Its autonomy must not be weakened under any circumstances.

**OpenClaw** is a detachable orchestration/control layer. It orchestrates AshbelOS; it does not replace it. If OpenClaw is unavailable, AshbelOS must continue to operate independently.

**Claude bridge** (`engines/claude_dispatch.py`, `api/routes/claude_dispatch.py`) is an orchestration interface only — not business core. It may be removed without affecting core business execution.

---

## Sensitive Action Flow (Mandatory)

Every sensitive action must follow this exact sequence. No step may be skipped.

```
Intent → Preview → Approval → Execute → Audit Log
```

- **Intent:** system classifies the incoming command
- **Preview:** system generates a preview of the proposed action and surfaces it to the operator
- **Approval:** operator explicitly approves (or denies) via Dashboard or Telegram inline keyboard
- **Execute:** action is executed only after approval is recorded
- **Audit Log:** result is written to the approval audit trail

---

## Business Logic Residency

The following must remain native to AshbelOS and must not be relocated to external systems as source of truth:

- Business memory
- Lead scoring
- Revenue logic
- Israeli business adaptation (cultural adapter, policy engine)
- Critical execution fallback paths

These may be orchestrated externally but the source-of-truth implementation stays in this repo.

---

## Fallback Policy

Critical execution paths must support AshbelOS-native fallback.

If any external bridge or orchestration layer (OpenClaw, Claude bridge, GPT connector, MCP endpoint) fails:
- Core business execution (leads, outreach, scoring) must remain possible through AshbelOS directly via `POST /api/command`
- The orchestrator must not be blocked by external bridge failures
- The executor `_HANDLERS` dict must remain self-contained

---

## Wave One External Channels

**Approved for active execution:** Telegram only.

Telegram is the sole approved inbound and outbound execution channel. The webhook at `POST /api/telegram/webhook` handles both text commands and inline approval callbacks.

---

## Excluded from Active Approved Scope

The following must not be introduced or expanded without explicit approval:

| Area | Status |
|------|--------|
| WhatsApp execution | Route exists (`api/routes/whatsapp.py`); must not be expanded |
| Email execution | Not approved |
| Calendar execution | Not approved |
| Remote file writes | Not approved |
| Additional external connectors | Not approved |
| New infrastructure beyond current approved phase | Not approved |

**Note on WhatsApp:** The route exists as a legacy scaffold. The `outreach_engine.py` has WhatsApp send logic. This code must not be actively triggered through new automation. Cultural adaptation applies when outreach is manually executed.

---

## Business Context Lock

This system operates exclusively for **אשבל אלומיניום (Ashbal Aluminum)**.

- Active profile: `ashbel` (`BUSINESS_ID=ashbel`)
- Sector: Aluminum
- No other business profile may be activated
- The `demo_real_estate` scaffold in `config/business_registry.py` must remain inactive

---

## Source-of-Truth Mapping

| Document | Role | Binding |
|----------|------|---------|
| `docs/ashbelos-governance.md` (this file) | Source of truth — governance | Yes |
| `docs/ashbelos-token-efficiency-policy.md` | Source of truth — token policy | Yes |
| `CLAUDE.md` | Adapter — governance + token policy + session log | Yes |
| `.github/copilot-instructions.md` | Adapter — Copilot context | Yes |
| `.claude/skills/ashbelos/SKILL.md` | Operational reference | Yes |
| `README.md` | Public project overview | No |
| `docs/AGENT.md` | Agent contract reference | Yes |
| `docs/TELEGRAM.md` | Telegram integration spec | Yes |
| `docs/FALLBACK.md` | Fallback and failure mode spec | Yes |
| `docs/INTEGRATIONS.md` | Connector inventory | Yes |
| `docs/API.md` | API contract | Informational |
| `docs/DEPLOY.md` | Deploy runbook | Operational |
| `.env.example` | ENV var reference | Operational |
