# AshbelOS — Product Operating Model

> Source of truth for product shape, UX philosophy, screen hierarchy, and operator experience.
> All UI changes must comply with this document.
> **Updated: 2026-04-18 — Scope Reset v2.0**

---

## Product Identity

**AshbelOS is a general business operating system — profile-driven.**
The active business profile (set via `BUSINESS_ID`) determines domain-specific behavior.
Currently active: `ashbel` (Ashbal Aluminum — אשבל אלומיניום).

AshbelOS is the daily work surface for any business operator:
**discover → qualify → contact → close → learn**

It is not a dashboard, a CRM viewer, or a reporting tool.
It is the primary operating console: goals drive agents, agents drive actions, actions drive revenue.

---

## Core UX Contract (Mandatory)

Every active screen must answer these four questions visibly:

| # | Question | UI Element |
|---|----------|-----------|
| 1 | What is the current state? | Widget bar + insight strip |
| 2 | What matters now? | Highlighted items / sorted list |
| 3 | What is recommended next? | Insight chip with reasoning |
| 4 | What is the primary action? | `UI.nextAction()` CTA button |

No screen is considered complete without all four.

---

## Screen Hierarchy

### Primary Work Surfaces (daily use, prominent nav)
| Screen | Purpose |
|--------|---------|
| Home | Daily work surface: command bar, urgent actions, hot leads, approvals, revenue queue, learning signals |
| Leads | Action-centric lead operating surface with briefing and draft |
| Discovery | Business goal → source scan → ranked candidates → recommended actions |
| Upload/Import | File intake → classify → preview → commit |
| Tasks | Task queue with agent dispatch visibility |
| Approvals | Governed approval flow for sensitive actions |
| Communications | Outreach queue, follow-up management, channel status |
| Agents | Operating actors: status, last run, last result, next action |
| Briefing | Real-time caller/lead briefing and action surface |
| CRM/Clients | Active deals and won clients |

### Secondary / Admin Surfaces (visible but de-emphasized)
| Screen | Purpose |
|--------|---------|
| Revenue Plan | Daily time allocation and pipeline value |
| Calendar | Weekly schedule and events |
| Pipeline | Outbound pipeline state |
| Goals | Goal tracking |
| Reports | Historical reporting |
| SEO | Website and content growth |
| Channels | Channel readiness and manual send workflow |
| Settings | System configuration |
| Dashboard | System health and admin metrics |

---

## Channel UX Rules

Every channel surface must show:
1. Current channel status (ready / readiness-only / blocked)
2. Draft generation CTA (always available)
3. Manual send workflow (always available — fallback when automation blocked)
4. Execution status when automated sending is active

Manual send workflow: Generate draft → show preview → copy button + channel link → operator sends manually → mark as sent.

---

## Guided Empty States (Mandatory)

No screen may show a blank/dead empty state. Every empty state must include:
1. Why it is empty (one line)
2. A CTA button: what to press now
3. What will happen next (button label explains)

Use `UI.guidedEmpty(msg, icon, ctaLabel, ctaJs)` for all empty states.

---

## Drafting Flow (Governed)

All outreach drafts must follow:
`Lead/Goal → Draft Request → Context Pack → Model Call → Preview → Approval → Store/Send`

- `POST /api/lead_ops/draft` is the canonical drafting endpoint
- `DraftModal` component handles all draft UX
- All drafts `requires_approval: true` — no unsupervised sending

---

## Marketing and SEO UX

The marketing/SEO surface operates for the **business website** (not AshbelOS itself):
- Analyze → detect gaps → recommend → draft → preview → approval → execute/export
- Weekly marketing recommendations driven by learning engine
- SEO content: titles, meta, schema, city pages, blog posts, image prompts
- Marketing: offers, campaign ideas, social post drafts, seasonal recommendations

---

## Command-First UX (Mandatory)

The home panel must always show a command bar at the top.
Any operator can type a natural language command at any time.
Result appears inline, with approval gate when action is sensitive.
No screen should require more than 3 taps to reach the primary action.
