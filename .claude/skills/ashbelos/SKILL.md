# AshbelOS Claude Code Skill

## Project Identity
- **Product:** AshbelOS — Autonomous Business Operating System
- **Business:** אשבל אלומיניום (Ashbal Aluminum) — aluminum windows, doors, pergolas
- **Sector:** Aluminum, Israeli market
- **Runtime:** Flask + Gunicorn, PostgreSQL, Railway
- **Language:** Python 3.11 | Hebrew UI | ILS currency
- **Production:** https://ashbel-os-production.up.railway.app
- **Branch model:** `master` = production-ready

---

## Architecture Map

```
Telegram / Dashboard UI
        ↓
api/routes/*.py                 (Flask Blueprints, all at url_prefix='/api')
        ↓
orchestration/orchestrator.py   (Intent → Task via _INTENT_TASK_MAP)
        ↓
orchestration/task_manager.py   (Task lifecycle: dispatch → execute → complete/fail)
        ↓
services/execution/executor.py  (_HANDLERS dict — module-level, after all _handle_* funcs)
        ↓
agents/**  /  engines/*.py      (Domain logic)
        ↓
services/storage/               (PostgreSQL via SQLAlchemy)
        ↓
memory/sessions/                (Token usage, agent decisions, session logs)
```

### Key Contracts
- `OrchestratorResult` is a `@dataclass` — use `.message`, `.intent`, `.success`
- `orchestrator` = module-level singleton — never instantiate per-request
- `task_manager.dispatch()` owns full task lifecycle
- `_HANDLERS` defined AFTER all `_handle_*` functions in executor.py

---

## Phase 12 — Lead Acquisition OS Skills

All skills are stateless, contract-based, importable as pure Python. No DB inside skill functions.

| Skill Module | File | Key Functions |
|---|---|---|
| Source Discovery | `skills/source_discovery.py` | `discover_sources(goal)`, `detect_source_types(goal)`, `suggest_communities(segment)`, `build_search_intents(goal, segment)`, `rank_sources(sources, segment)`, `explain_source_strategy(plan)` |
| Lead Intelligence | `skills/lead_intelligence.py` | `normalize(raw)`, `extract_candidates(signals)`, `deduplicate(leads, existing)`, `enrich(lead)`, `score_lead(enriched)`, `rank_leads(scored)`, `explain_fit(lead, goal)` |
| Outreach Intelligence | `skills/outreach_intelligence.py` | `choose_action(lead, ctx)`, `choose_channel(lead, ctx)`, `choose_timing(lead, ctx)`, `draft_first_contact(lead)`, `draft_followup(lead)`, `draft_meeting_request(lead)`, `draft_inbound_response(lead, text)`, `draft_comment_reply(comment, lead)` |
| Israeli Context | `skills/israeli_context.py` | `get_hebrew_tone(segment)`, `is_good_timing(dt)`, `get_best_send_window()`, `get_holiday_context()`, `local_signal_detection(text)`, `geo_fit(city)`, `compliance_hints(channel)` |
| Workflow | `skills/workflow_skills.py` | `build_work_queue(leads)`, `mark_approval_required(item, reason)`, `push_to_crm(lead)`, `update_lead_status(id, status)`, `queue_next_action(id, action)` |
| Website Growth | `skills/website_growth.py` | `site_audit(url, html)`, `seo_intelligence(audit)`, `content_gap_detection(audit, segment)`, `landing_page_suggestions(audit)`, `lead_capture_review(audit)`, `content_draft(topic, city)`, `priority_planner(audit, gaps)` |

### Acquisition Engine
`engines/lead_acquisition_engine.py` — orchestrates all skills into a full pipeline.
- `run_acquisition(goal, signals)` → `AcquisitionResult`
- `process_inbound(lead_data)` → `lead_id`
- `run_website_analysis(url, html)` → `WebsiteAnalysisResult`

### Lead Ops API
`/api/lead_ops/*` — 10 endpoints (see `docs/API.md`)
- Phase 14: `brief/<id>`, `batch_score`, `execute/<id>` added

### New Intents
`DISCOVER_LEADS`, `PROCESS_INBOUND`, `WEBSITE_ANALYSIS`, `LEAD_OPS_QUEUE`

### New Event Types
`LEAD_DISCOVERED`, `INBOUND_LEAD_RECEIVED`, `LEAD_OUTREACH_SENT`, `LEAD_FOLLOWUP_PROPOSED`, `WEBSITE_ANALYSIS_REQUESTED`

---

## Agents

| Agent | File | task_type | action |
|-------|------|-----------|--------|
| LeadAcquisitionAgent | sales/lead_acquisition_agent.py | acquisition | * (all 4 actions) |
| LeadQualifierAgent | sales/lead_qualifier.py | scoring | score_lead |
| MessagingAgent | sales/messaging_agent.py | sales | generate_content |
| CEOAgent | executive/ceo_agent.py | strategy | ceo_decision |
| ChiefOfStaffAgent | executive/chief_of_staff_agent.py | executive | plan_action |
| MaintenanceAgent | executive/maintenance_agent.py | executive | maintenance_report |
| GenericTaskAgent | generic/task_agent.py | * | * (fallback) |

### LeadAcquisitionAgent Details (Phase 13)
- `discover_leads`: local-first (empty signals → plan only), Haiku batch signal pre-filter, calls `run_acquisition()`
- `process_inbound`: calls `process_inbound()` + Sonnet AI-personalised Hebrew draft (cached system prompt)
- `website_analysis`: calls `run_website_analysis()`
- `lead_ops_queue`: direct DB read, 0 tokens

### Token Routing
- **Haiku** (`claude-haiku-4-5`): classification, routing, scoring — task_type routing/classification/crm
- **Sonnet** (`claude-sonnet-4-6`): drafting, outreach, content — task_type sales/outreach/content
- **Opus** (`claude-opus-4-6`): strategy, complex reasoning — task_type strategy/analysis

---

## Engines

| Engine | File | Purpose |
|--------|------|---------|
| lead_engine | engines/lead_engine.py | Lead scoring, compute_score() |
| outreach_engine | engines/outreach_engine.py | execute_outreach(), WhatsApp/email |
| revenue_engine | engines/revenue_engine.py | Pipeline, weighted value |
| seo_engine | engines/seo_engine.py | Meta, city pages, blog, image prompts |
| dashboard_engine | engines/dashboard_engine.py | Summary, bottlenecks, hot leads |
| reporting_engine | engines/reporting_engine.py | Daily text report |

---

## Services

| Service | Path | Purpose |
|---------|------|---------|
| policy_engine | services/policy/policy_engine.py | check_timing/quota/compliance (0 tokens) |
| cultural_adapter | services/integrations/cultural_adapter.py | Israeli message adaptation |
| telegram_service | services/telegram_service.py | send(), send_approval_request() |
| gmail_listener | services/integrations/gmail_listener.py | scan_inbox() |
| lead_scraper | services/integrations/lead_scraper.py | scrape(city, category) |
| cost_tracker | routing/cost_tracker.py | flush_to_session_log(agent_name) |
| model_router | routing/model_router.py | call(), call_batch() |

---

## API Routes

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| GET | /api/health | No | Health check |
| POST | /api/command | Yes | NLP command dispatcher |
| GET | /api/leads | Yes | List leads |
| GET | /api/crm/deals | Yes | List deals |
| GET | /api/dashboard/summary | Yes | Revenue dashboard |
| GET | /api/admin/status | Yes | Business config + DB counts |
| GET | /api/admin/usage | Yes | Today's activity counts |
| GET | /api/seo/meta | Yes | SEO meta descriptions |
| GET | /api/seo/cities | Yes | City landing pages |
| GET | /api/seo/blog | Yes | Blog posts |
| GET | /api/seo/images | Yes | Adobe Firefly prompts |
| GET | /api/system/metrics | Yes | Agent call metrics |
| GET | /api/system/traces/{id} | Yes | Trace chain |
| POST | /api/telegram/webhook | Token | Inbound Telegram + callbacks |
| POST | /api/approvals/{id} | Yes | Resolve approval |

---

## Governance Rules

> Source of truth: `docs/ashbelos-governance.md`. Rules below are a summary.

1. Business context locked to Ashbal Aluminum only
2. Approved external channel: **Telegram only** (Wave One) — see `docs/TELEGRAM.md`
3. WhatsApp execution route exists but must not be expanded — see `docs/INTEGRATIONS.md`
4. Sensitive action flow: **Intent → Preview → Approval → Execute → Audit Log**
5. Business logic stays native to AshbelOS (lead scoring, revenue logic, Israeli adaptation)
6. Fallback paths must work without external bridges — see `docs/FALLBACK.md`

---

## How to Add a New Agent

```python
# 1. Create file: agents/departments/{dept}/{name}_agent.py
class MyAgent(BaseAgent):
    agent_id   = "builtin_my_agent_v1"
    name       = "My Agent"
    department = "sales"  # or executive, generic
    version    = 1

    def can_handle(self, task_type: str, action: str) -> bool:
        return task_type == "sales" and action == "my_action"

    def execute(self, task: TaskModel) -> ExecutionResult:
        try:
            # local-first check
            local = self._local_compute(task)
            if local: return local
            # AI call
            result = self._ai_call("sales", SYSTEM, user_prompt, priority="balanced")
            return ExecutionResult(success=True, message=result, output={})
        except Exception as e:
            return ExecutionResult(success=False, message=str(e), output={})

# 2. Register in agents/base/agent_registry.py bootstrap()
# 3. Add Intent in orchestration/intent_parser.py
# 4. Add to _INTENT_TASK_MAP in orchestration/orchestrator.py
# 5. pytest — all pass
# 6. commit
```

---

## How to Add a New Intent

```python
# orchestration/intent_parser.py — Intent enum
INTENT_NAME = "intent_key"

# IntentParser._classify() — add before Sales fallback:
if any(w in tl for w in ["trigger phrase", "another trigger"]):
    return Intent.INTENT_NAME, 0.9

# orchestration/orchestrator.py — _INTENT_TASK_MAP:
Intent.INTENT_NAME: ("task_type", "action"),
```

---

## Token Optimization Rules
1. **Local-first:** check `_local_compute()` before any AI call
2. **Model routing:** Haiku→routing/classify, Sonnet→content/draft, Opus→strategy
3. **Prompt caching:** pass `use_cache=True` to `_ai_call()` for repeated system prompts
4. **Batch:** use `model_router.call_batch(prompts)` for multi-lead processing
5. **Log costs:** `cost_tracker.flush_to_session_log(agent_name)` after AI calls

---

## Testing Patterns

```bash
# Run all tests
venv/Scripts/python.exe -m pytest tests/ -q

# Must be green before every commit
# Test files: tests/test_executor_bootstrap.py, test_runtime_flow_axis1.py,
#             test_core_flow.py, test_openclaw_bridge.py
```

---

## Deployment Checklist
- [ ] pytest 79/79 green
- [ ] `GET /api/health` → 200 `{"db": true}`
- [ ] `POST /api/command {"command":"הצג לידים"}` → 200
- [ ] Railway env vars: OS_API_KEY, DATABASE_URL, TELEGRAM_BOT_TOKEN,
      TELEGRAM_CHAT_ID, WEBHOOK_VERIFY_TOKEN, ANTHROPIC_API_KEY
- [ ] push to master → Railway auto-deploys

---

## Current Phase Status

| Phase | Feature | Commit | Status |
|-------|---------|--------|--------|
| 1–10 (Batches) | CRM, Revenue, Outreach, Mobile, Admin | 724579f | ✅ |
| Token Optimization | Model routing, cache_control, batch, session log | cb75569 | ✅ |
| Policy | business_knowledge + policy_engine | 4ef9976 | ✅ |
| Chief of Staff | ChiefOfStaffAgent + Intent.CHIEF_OF_STAFF | c03d86b | ✅ |
| Telegram Approval | Inline keyboard approve/deny/edit | a17ac7f | ✅ |
| Cultural Adapter | Israeli message adaptation | 2134b32 | ✅ |
| Lead Sourcing | GmailListener + LeadScraper + scheduler | 8c9db53 | ✅ |
| Maintenance Agent | Weekly health report + CLAUDE.md | 90b6e0c | ✅ |
| Observability | StructuredLogger + MetricsCollector + TraceStore | cd667d0 | ✅ |
| SEO Engine | City pages + blog + image prompts | b01556d | ✅ |

---

## Efficient Execution Rules

- Use this skill as operational baseline before broad repo inspection.
- Prefer current system structure (agents, routes, hooks, docs) over re-analysis.
- Use metadata-first approach for external capabilities.
- External capabilities must be evaluated and adapted, not treated as source of truth.
- Runtime completion requires real proof: working routes, active hooks, approval flow, execution path, and deploy verification.
- Natural language system-change requests require preview and approval before execution.
- Block any change that creates duplication, replaces working flows, or bypasses governance.
