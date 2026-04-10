# AshbelOS — AGENTS.md
> Onboarding file for Claude Cowork, Claude Code, and any AI agent joining this repo.
> Read this file first. Do not scan the entire codebase before reading this.

---

## Who You Are Working For

**Business:** אשבל אלומיניום (Ashbal Aluminum)
**Location:** ניצני עוז, Israel
**Sector:** Aluminum manufacturing — windows, doors, pergolas, facades
**Customers:** Contractors (קבלנים), Architects (אדריכלים), Private builders
**Language:** Hebrew (he) for all UI, business logic, and communications
**Currency:** ILS | Average deal size: 15,000 ILS

> This is a real production system serving a real business. No demo data. No mock profiles.

---

## What You Are Building

**AshbelOS** — Autonomous Business Operating System.
Multi-agent AI platform for CRM, outreach, lead scoring, and revenue intelligence.
Operated via Hebrew commands through Telegram, Web UI, or REST API.

**Production URL:** https://ashbel-os-production.up.railway.app
**Health check:** GET /api/health returns status ok and db true

---

## Architecture

```
Telegram / Dashboard UI / REST API
        down
api/routes/*.py              Flask Blueprints, prefix /api
        down
orchestration/orchestrator.py      Intent to task_type + action
        down
orchestration/task_manager.py      lifecycle: queued to started to done/fail
        down
services/execution/executor.py     _HANDLERS dict (module-level, after all _handle_* functions)
        down
agents/** and engines/*.py         Business logic
        down
services/storage/ (PostgreSQL)     SQLAlchemy models + repositories
```

### Key Contracts — Never Break These
- OrchestratorResult is a dataclass — use .message, .intent, .success
- orchestrator (lowercase) = module-level singleton — never instantiate per-request
- task_manager.dispatch() owns full task lifecycle — never call mark_completed/mark_failed elsewhere
- _HANDLERS in executor.py defined AFTER all _handle_* functions — never move above them

---

## Active Agents

| Agent | Purpose | Model |
|-------|---------|-------|
| ChiefOfStaffAgent | Strategic planning, goal to action plan | Opus |
| CEOAgent | Complex reasoning, market analysis | Opus |
| LeadQualifierAgent | Lead scoring, LEAD_SCORED events | Haiku |
| MessagingAgent | Outreach content generation | Sonnet |
| MaintenanceAgent | Weekly health report, self-improvement | Sonnet |
| ExecutiveAssistantAgent | Drafts, meetings, reminders | Sonnet |
| GenericTaskAgent | Fallback for unknown task types | Haiku |

---

## Business Knowledge

### Israeli Timing Rules (config/business_knowledge.py)
- BLOCKED: Friday after 13:00, Saturday all day, before 08:00 any day
- BEST: Sunday 08-10 (contractors), Tuesday 10-12 (architects), Thursday 09-11

### Audience Playbook
| Audience | Tone | Hook | Opening |
|----------|------|------|---------|
| contractors | Direct | Price + delivery time | היי {name}, |
| architects | Professional | Portfolio + quality | שלום {name}, |
| private | Friendly | Free visit + warranty | היי {name}, |
| general | Neutral | Introduction + value | שלום {name}, |

### Service Areas
ישובי השומרון ובנימין | השרון | מרכז הארץ | אשדוד עד זכרון יעקב

---

## Governance — Binding Rules

### Source of Truth
ashbelos-governance.md > CLAUDE.md > AGENTS.md

### Sensitive Action Flow (mandatory)
Intent to Preview to Approval to Execute to Audit Log
No sensitive action may skip Preview or Approval.

### Approved External Channels (Wave One)
Telegram only. WhatsApp = deeplink only, no automated sending.

### Excluded Without Explicit Approval
- WhatsApp automated execution
- Email execution
- Calendar execution
- Remote file writes
- Additional external connectors

---

## Token Optimization — Always Apply

1. _local_compute() first — Python, zero tokens
2. Haiku for routing and classification — cheap
3. Sonnet for content drafting and lead analysis
4. Opus for strategy and complex reasoning only

Models: Haiku = claude-haiku-4-5-20251001 | Sonnet = claude-sonnet-4-6 | Opus = claude-opus-4-6
Use cache_control on all repeated system prompts.

---

## Current Status

Version: v2.0 | master = production-ready
Tests: 79/79 passing
CI: Auto push to master triggers pytest, then Railway deploy, then health check

### Completed Phases
- Phase 1: Telegram inbound webhook + datetime fix
- Phase 2: Business knowledge + Policy engine + Token optimization
- CI: Auto-trigger on push to master

### Next Phases (in order)
- Phase 3: Chief of Staff Agent
- Phase 4: Telegram approval inline buttons
- Phase 5: Cultural adapter
- Phase 6: Gmail listener + Maps scraper (needs governance approval)
- Phase 7: Maintenance agent
- Phase 8: Observability — logging, metrics, tracing
- Phase 9: SEO Engine full implementation
- Phase 10: AshbelOS Skill file

---

## How To Work

### Before Starting Any Task
1. Read CLAUDE.md for full project context
2. Read ashbelos-governance.md for binding rules
3. Check memory/sessions/ for recent session logs
4. Run: DATABASE_URL=sqlite:///:memory: API_KEY=test pytest tests/ -q

### Rules
- One file per commit — enables precise rollback
- pytest must pass before every commit — no exceptions
- CLAUDE.md: append only, never overwrite existing content
- Local-first: _local_compute() before any AI call
- Small steps: complete current phase before expanding scope
- Log every session to memory/sessions/YYYY-MM-DD.md

### Adding a New Agent
1. Create agents/departments/{dept}/{name}_agent.py extending BaseAgent
2. Implement _local_compute() hook — return None to proceed to AI
3. Register in agents/base/agent_registry.py
4. Add Intent in orchestration/intent_parser.py
5. Map in orchestrator._INTENT_TASK_MAP
6. Add tests/test_{name}_agent.py
7. pytest must pass, then commit

### Adding a New Intent
1. Add to Intent enum in intent_parser.py
2. Add trigger keywords in _detect_intent()
3. Map in orchestrator._INTENT_TASK_MAP: Intent.NEW: ("task_type", "action")
4. pytest, then commit

### Stop Only For
- Missing credentials or external blocker
- Destructive risk (data loss, production breakage)
- Explicit governance violation
- pytest failure that cannot be resolved

---

## Environment Variables

| Variable | Purpose | Status |
|----------|---------|--------|
| DATABASE_URL | PostgreSQL — Railway auto-injects | Set |
| OS_API_KEY | API auth header | Set |
| ANTHROPIC_API_KEY | Claude models | Set |
| TELEGRAM_BOT_TOKEN | Telegram bot | Set |
| TELEGRAM_CHAT_ID | Operator chat ID | Set |
| WHATSAPP_ACCESS_TOKEN | WhatsApp API | Pending Meta approval |
| WHATSAPP_PHONE_NUMBER_ID | WhatsApp sender | Pending |
| AUTO_APPROVE_BELOW_RISK | Risk threshold 1-5 | Default: 3 |

---

## Memory Structure

memory/sessions/YYYY-MM-DD.md — what was done each session
memory/decisions/YYYY-MM-DD.md — why decisions were made
memory/knowledge/ — learned patterns and improvements

MaintenanceAgent reads memory weekly on Sunday at 07:00 IL and proposes improvements.

---

## Deployment

Tests: DATABASE_URL=sqlite:///:memory: API_KEY=test pytest tests/ -q
Production: git push origin master
  CI runs pytest 79/79
  Railway auto-deploys
  GET /api/health verified as 200

---

*AshbelOS v2.0 | April 2026*
