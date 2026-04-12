# AshbelOS — Product Operating Model

> Source of truth for product shape, UX philosophy, screen hierarchy, and operator experience.
> All UI changes must comply with this document.

---

## Product Identity

AshbelOS is a **guided business operating console** for Ashbal Aluminum.
It is not a dashboard, a CRM viewer, or a reporting tool.
It is the daily work surface for the operator: discover → qualify → contact → close → learn.

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
| Home | Daily work surface: urgent actions, hot leads, approvals, system status, entry to discovery + import |
| Leads | Action-centric lead operating surface |
| Discovery | Business goal → source scan → ranked candidates → recommended actions |
| Upload/Import | File intake → classify → preview → commit |
| Tasks | Task queue with agent dispatch visibility |
| Approvals | Governed approval flow for sensitive actions |
| Communications | Outreach queue, follow-up management, pipeline state |
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
| Settings | System configuration |
| Dashboard | System health and admin metrics |

---

## Guided Empty States (Mandatory)

No screen may show a blank/dead empty state.
Every empty state must include:
1. Why it is empty (one line)
2. A CTA button: what to press now
3. What will happen next (button label explains)

Use `UI.guidedEmpty(msg, icon, ctaLabel, ctaJs)` for all empty states.

---

## Drafting Flow (Governed)

All outreach drafts must follow: Lead/Goal → Draft Request → Context Pack → Model Call → Preview → Approval → Store/Send

- `POST /api/lead_ops/draft` is the canonical drafting endpoint
- `DraftModal` component handles all draft UX
- All drafts `requires_approval: true` — no unsupervised sending
- Draft results must be stored or submitted for approval before any channel action

---

## Agent Visibility

Agents must be visible as operating business actors, not hidden in code.
The Agents panel must show: name, department, role, status, last_active, tasks_done, model_preference.
Agent cards must link to relevant Leads and Tasks panels.

---

## Discovery Model

Discovery is a business workflow, not a search box:
1. Goal input (natural Hebrew business language)
2. Segment decomposition (who to find)
3. Source selection (where to look)
4. Search intent generation (what to search for)
5. Community/channel identification (groups, directories, platforms)
6. Result ranking with confidence and recommended approach
7. Action surface: add to CRM / create task / draft outreach / follow-up

Source visibility is required: show which sources were scanned, how many found, how many passed.

---

## Mobile-First Rules

See `docs/UI_UX_MOBILE_RULES.md` for full spec.
Summary:
- Sidebar closed by default on ≤640px
- Cards/lists preferred over dense tables
- Minimum tap target: 40px height
- Single-column layout on mobile
- No horizontal scroll within panels

---

## Learning Loop

User actions (approvals, rejections, outreach outcomes) feed back into:
- `skills/learning_skills.py` (template/source/agent tracking)
- `MemoryStore` (pattern storage)
- Lead scoring adjustments
- Model routing overrides

This loop is automatic and does not require user configuration.
