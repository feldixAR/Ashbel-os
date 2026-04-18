# AshbelOS Governance Document

> **Source of truth for all governance decisions.**
> CLAUDE.md §Governance Policy is an adapter of this document. If conflict exists, this document wins until CLAUDE.md is corrected.
> **Updated: 2026-04-18 — Scope Reset v2.0**

---

## Product Identity

**AshbelOS is a general business operating system.**
The active business profile drives all domain-specific behavior: tone, channels, lead types, templates, playbooks, SEO context, and recommendations.

- **Current active profile:** `ashbel` (Ashbal Aluminum — אשבל אלומיניום)
- Active profile is set via `BUSINESS_ID` env var (default: `ashbel`)
- Adding new profiles extends the system; it does not change the product identity
- `demo_real_estate` in `config/business_registry.py` remains inactive scaffold

---

## Product Layers

**AshbelOS** is the independent business core. Its autonomy must not be weakened under any circumstances.

**OpenClaw** is a detachable orchestration/control layer. It orchestrates AshbelOS; it does not replace it. If OpenClaw is unavailable, AshbelOS must continue to operate independently.

**Claude bridge** (`engines/claude_dispatch.py`, `api/routes/claude_dispatch.py`) is an orchestration interface only — not business core.

---

## Sensitive Action Flow (Mandatory — Preserved)

Every sensitive action must follow this exact sequence. No step may be skipped.

```
Intent → Preview → Approval → Execute → Audit Log
```

- **Intent:** system classifies the incoming command
- **Preview:** system generates a preview of the proposed action and surfaces it to the operator
- **Approval:** operator explicitly approves (or denies) via Dashboard or Telegram inline keyboard
- **Execute:** action is executed only after approval is recorded
- **Audit Log:** result is written to the approval audit trail

This flow is non-negotiable regardless of channel or agent.

---

## Business Logic Residency

The following must remain native to AshbelOS and must not be relocated to external systems as source of truth:

- Business memory and profile data
- Lead scoring and qualification logic
- Revenue logic and pipeline state
- Cultural/language adaptation (Israeli business context)
- Critical execution fallback paths

These may be orchestrated externally but the source-of-truth implementation stays in this repo.

---

## Fallback Policy

Critical execution paths must support AshbelOS-native fallback.

If any external bridge or orchestration layer fails:
- Core business execution (leads, outreach, scoring) must remain possible through `POST /api/command`
- The orchestrator must not be blocked by external bridge failures
- The executor `_HANDLERS` dict must remain self-contained

---

## External Channels — Updated Scope

### Operator Channels (internal control)
| Channel | Status | Notes |
|---------|--------|-------|
| Telegram | **Active — operator only** | Inbound commands, approval callbacks, alerts |
| Dashboard | **Active** | Primary UI |

### Customer Outreach Channels — Readiness Layers
| Channel | Implementation Status | Execution Status |
|---------|----------------------|-----------------|
| Manual Send | **Fully implemented** | Active — operator sends manually |
| WhatsApp | **Readiness layer** | Draft + deep link only; actual sending blocked until Meta credentials provided |
| Email | **Readiness layer** | Draft + preview + MIME build; actual sending blocked until SMTP credentials provided |
| Meta (Facebook/Instagram) | **Readiness layer** | Content draft + preview; execution blocked until Meta Business API credentials |
| LinkedIn | **Compliant readiness layer** | Content draft + preview; API posting blocked until LinkedIn API credentials |
| SMS | **Readiness layer** | Draft only; blocked until SMS provider credentials |

### Channel Readiness Definition
A channel is "readiness layer" when:
1. Draft generation is fully implemented and produces real content
2. Preview and approval flow are wired
3. Manual send workflow exists so operator can execute without automation
4. Execution is blocked only on external credentials/account approval
5. The code infrastructure is in place for instant activation when credentials arrive

---

## Business Profile Layer

The business profile (`config/business_registry.py`) drives:
- Tone and language of outreach templates
- Lead types, scoring weights, target segments
- Channel priority order
- SEO context: site URL, target keywords, city pages, blog topics
- Marketing playbook: offers, messages, seasonal campaigns
- Competitor context
- Avg deal size and revenue math

Adding a new business profile requires:
1. Adding a `BusinessProfile` entry to `BUSINESS_PROFILES` dict
2. Setting `BUSINESS_ID` env var
3. No code changes — engine reads profile at runtime

---

## Source-of-Truth Mapping

| Document | Role | Binding |
|----------|------|---------|
| `docs/ashbelos-governance.md` (this file) | Source of truth — governance | Yes |
| `docs/ashbelos-token-efficiency-policy.md` | Source of truth — token policy | Yes |
| `CLAUDE.md` | Adapter — governance + session log | Yes |
| `docs/PRODUCT_OPERATING_MODEL.md` | Product shape, UX contract | Yes |
| `docs/AGENTS_SKILLS_ORCHESTRATION.md` | Agent/skill contracts | Yes |
| `docs/UI_UX_MOBILE_RULES.md` | Design system, mobile rules | Yes |
| `docs/DEPLOY_AND_VERIFICATION_DISCIPLINE.md` | Deploy/commit discipline | Yes |
| `docs/TELEGRAM.md` | Telegram integration spec | Yes |
| `docs/FALLBACK.md` | Fallback and failure mode spec | Yes |
| `docs/INTEGRATIONS.md` | Connector inventory | Yes |
