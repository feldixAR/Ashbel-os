# AshbelOS Claude Code Skill

## Project Identity
- **Product:** AshbelOS — Autonomous Business Operating System
- **Business:** אשבל אלומיניום (Ashbal Aluminum) — aluminum windows, doors, pergolas
- **Sector:** Aluminum, Israeli market
- **Runtime:** Flask + Gunicorn, PostgreSQL, Railway
- **Language:** Python 3.11 | Hebrew UI | ILS currency
- **Production:** https://ashbel-os-production.up.railway.app
- **Branch model:** `master` = production-ready
- **Current version:** v5.2 — Guided Operator Console (Phase 21)
- **Source of truth:** `CLAUDE.md` (always wins over this file)

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

## Phase Status (v5.2 — Phase 21 complete)

| Phase | Feature | Commit | Status |
|-------|---------|--------|--------|
| 1–10 (Batches) | CRM, Revenue, Outreach, Mobile, Admin | 724579f | ✅ |
| Token Optimization | Model routing, cache_control, batch, session log | cb75569 | ✅ |
| Policy | business_knowledge + policy_engine | 4ef9976 | ✅ |
| Chief of Staff | ChiefOfStaffAgent + Intent.CHIEF_OF_STAFF | c03d86b | ✅ |
| Telegram Approval | Inline keyboard approve/deny/edit | a17ac7f | ✅ |
| Cultural Adapter | Israeli message adaptation | 2134b32 | ✅ |
| Lead Sourcing | GmailListener + LeadScraper + scheduler | 8c9db53 | ✅ |
| Maintenance Agent | Weekly health report | 90b6e0c | ✅ |
| Observability | StructuredLogger + MetricsCollector + TraceStore | cd667d0 | ✅ |
| SEO Engine | City pages + blog + image prompts | b01556d | ✅ |
| 12 | Lead Acquisition OS — 6 skill modules, acquisition engine, 7 API endpoints | 665d8278 | ✅ |
| 13 | LeadAcquisitionAgent — registry-owned, Haiku batch, Sonnet inbound draft | 042fa00f | ✅ |
| 14 | Brief/batch-score/execute endpoints + approval execute flow + activity log | 331a3f1a | ✅ |
| 15 | Telegram hot-lead alerts (score≥70) + inbound approval cards | 73040d8d | ✅ |
| 16 | Channel-native intake normalizer + document intelligence + self-evolution | ef0e6671 | ✅ |
| 17 | Mission Control UI + learning skills + self-evolution branch flow | d391c7f4 | ✅ |
| 18 | Home panel, upload/intake modal, CSS UX completion | 96d6e9cb | ✅ |
| 19 | Mobile sidebar toggle, real discovery, overlay modal, mobile cards | 77ffc744 | ✅ |
| 20 | pytz fallback system-wide + guided UX pass (empty states, CTAs) | ac13d314 | ✅ |
| 21 | Guided operator console — DraftModal, per-row actions, approval create | e83633a | ✅ |

---

## Skills Inventory

All skills are stateless, contract-based, importable as pure Python. No DB inside skill functions.

| Skill Module | File | Key Functions |
|---|---|---|
| Source Discovery | `skills/source_discovery.py` | `discover_sources(goal)`, `detect_source_types(goal)`, `suggest_communities(segment)`, `build_search_intents(goal, segment)`, `rank_sources(sources, segment)`, `explain_source_strategy(plan)` |
| Lead Intelligence | `skills/lead_intelligence.py` | `normalize(raw)`, `extract_candidates(signals)`, `deduplicate(leads, existing)`, `enrich(lead)`, `score_lead(enriched)`, `rank_leads(scored)`, `explain_fit(lead, goal)`, `next_action(lead)` (learning-aware) |
| Outreach Intelligence | `skills/outreach_intelligence.py` | `choose_action(lead, ctx)`, `choose_channel(lead, ctx)`, `choose_timing(lead, ctx)`, `draft_first_contact(lead)`, `draft_followup(lead)`, `draft_meeting_request(lead)`, `draft_inbound_response(lead, text)`, `draft_comment_reply(comment, lead)` |
| Israeli Context | `skills/israeli_context.py` | `get_hebrew_tone(segment)`, `is_good_timing(dt)`, `get_best_send_window()`, `get_holiday_context()`, `local_signal_detection(text)`, `geo_fit(city)`, `compliance_hints(channel)` |
| Workflow | `skills/workflow_skills.py` | `build_work_queue(leads)`, `mark_approval_required(item, reason)`, `push_to_crm(lead)`, `update_lead_status(id, status)`, `queue_next_action(id, action)` |
| Website Growth | `skills/website_growth.py` | `site_audit(url, html)`, `seo_intelligence(audit)`, `content_gap_detection(audit, segment)`, `landing_page_suggestions(audit)`, `lead_capture_review(audit)`, `content_draft(topic, city)`, `priority_planner(audit, gaps)` |
| Learning Skills | `skills/learning_skills.py` | `track_template_outcome(template_id, approved)`, `track_source_strategy(source, outcome)`, `track_agent_metrics(agent_id, latency, success)`, `track_lead_conversion(score_bucket, converted)`, `get_model_routing_overrides()` |
| Document Intelligence | `skills/document_intelligence.py` | `parse_document(base64_content, mime_type)`, `classify_records(rows)` — CSV/Excel/Word/PDF/TXT, Hebrew+English column detection |

### Acquisition Engine
`engines/lead_acquisition_engine.py` — orchestrates all skills into a full pipeline.
- `run_acquisition(goal, signals)` → `AcquisitionResult`
- `process_inbound(lead_data)` → `lead_id`
- `run_website_analysis(url, html)` → `WebsiteAnalysisResult`

---

## Agents

| Agent | File | task_type | action | Model |
|-------|------|-----------|--------|-------|
| LeadAcquisitionAgent | `sales/lead_acquisition_agent.py` | acquisition | * (all 4 actions) | Haiku (classify/batch) + Sonnet (draft) |
| LeadQualifierAgent | `sales/lead_qualifier.py` | scoring | score_lead | Haiku |
| MessagingAgent | `sales/messaging_agent.py` | sales | generate_content | Sonnet |
| CEOAgent | `executive/ceo_agent.py` | strategy | ceo_decision | Opus |
| ChiefOfStaffAgent | `executive/chief_of_staff_agent.py` | executive | plan_action | Opus (strategy) + Haiku (classify) |
| MaintenanceAgent | `executive/maintenance_agent.py` | executive | maintenance_report | Sonnet |
| GenericTaskAgent | `generic/task_agent.py` | * | * | Sonnet (fallback) |

### LeadAcquisitionAgent Details
- `discover_leads`: local-first (empty signals → plan only, 0 tokens), Haiku batch signal pre-filter, calls `run_acquisition()`; live learning hooks
- `process_inbound`: calls `process_inbound()` + Sonnet AI-personalised Hebrew draft (cached system prompt)
- `website_analysis`: calls `run_website_analysis()`
- `lead_ops_queue`: direct DB read, 0 tokens

### Token Routing
- **Haiku** (`claude-haiku-4-5-20251001`): classification, routing, scoring
- **Sonnet** (`claude-sonnet-4-6`): drafting, outreach, content
- **Opus** (`claude-opus-4-6`): strategy, complex reasoning

---

## Intents (orchestration/intent_parser.py)

| Intent | Maps To | Since |
|--------|---------|-------|
| DISCOVER_LEADS | acquisition/discover_leads | Phase 12 |
| PROCESS_INBOUND | acquisition/process_inbound | Phase 12 |
| WEBSITE_ANALYSIS | acquisition/website_analysis | Phase 12 |
| LEAD_OPS_QUEUE | acquisition/lead_ops_queue | Phase 12 |
| DOCUMENT_UPLOAD | acquisition/parse_document | Phase 16 |
| SYSTEM_CHANGE | executive/preview_system_change | Phase 16 |

---

## Executor Handlers (_HANDLERS in executor.py)

Key handlers added through Phase 21:
- `_handle_parse_document` — base64 → document_intelligence.parse_document() → process_inbound per record
- `_handle_preview_system_change` — classify → preview → ApprovalModel → Telegram card

---

## Engines

| Engine | File | Purpose |
|--------|------|---------|
| lead_engine | `engines/lead_engine.py` | Lead scoring, compute_score() |
| lead_acquisition_engine | `engines/lead_acquisition_engine.py` | Full acquisition pipeline |
| outreach_engine | `engines/outreach_engine.py` | execute_outreach(), WhatsApp/email |
| revenue_engine | `engines/revenue_engine.py` | Pipeline, weighted value |
| seo_engine | `engines/seo_engine.py` | Meta, city pages, blog, image prompts |
| dashboard_engine | `engines/dashboard_engine.py` | Summary, bottlenecks, hot leads |
| reporting_engine | `engines/reporting_engine.py` | Daily text report |
| phase11_engine | `engines/phase11_engine.py` | Revenue queue scoring (Phase 11 source of truth) |

---

## Services

| Service | Path | Purpose |
|---------|------|---------|
| policy_engine | `services/policy/policy_engine.py` | check_timing/quota/compliance (0 tokens) |
| cultural_adapter | `services/integrations/cultural_adapter.py` | Israeli message adaptation |
| telegram_service | `services/telegram_service.py` | send(), send_approval_request(), hot-lead alerts |
| gmail_listener | `services/integrations/gmail_listener.py` | scan_inbox() |
| lead_scraper | `services/integrations/lead_scraper.py` | scrape(city, category) |
| cost_tracker | `routing/cost_tracker.py` | flush_to_session_log(agent_name) |
| model_router | `routing/model_router.py` | call(), call_batch() |
| normalizer | `services/intake/normalizer.py` | normalize_telegram() — channel-agnostic multi-modal intake: text/document/voice/contact/video/poll/reply/forward → IntakePayload |

---

## API Routes

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| GET | `/api/health` | No | Health check |
| GET | `/api/version` | No | Commit + environment |
| POST | `/api/command` | Yes | NLP command dispatcher → orchestrator |
| GET | `/api/system/metrics` | Yes | Agent call metrics snapshot |
| GET | `/api/system/traces/<id>` | Yes | Trace chain |
| GET | `/api/system/pending_changes` | Yes | Pending self-evolution system changes |
| GET | `/api/leads` | Yes | List leads |
| POST | `/api/leads` | Yes | Create lead |
| PATCH | `/api/leads/<id>` | Yes | Update lead |
| GET | `/api/crm/deals` | Yes | List active deals |
| GET | `/api/crm/leads/<id>/full` | Yes | Lead with activities + timeline |
| GET | `/api/crm/leads/<id>/activities` | Yes | Activity log |
| POST | `/api/crm/leads/<id>/activities` | Yes | Log activity |
| GET | `/api/daily_revenue_queue` | Yes | Scored revenue priority queue |
| GET | `/api/dashboard/summary` | Yes | Revenue snapshot + AI recs |
| GET | `/api/approvals` | Yes | List pending approvals |
| POST | `/api/approvals/<id>` | Yes | Resolve approval (approve/deny) |
| POST | `/api/approvals/create` | Yes | Create UI-initiated approval request |
| GET | `/api/outreach/queue` | Yes | Pending outreach queue |
| POST | `/api/outreach/execute` | Yes | Execute outreach task |
| GET | `/api/outreach/summary` | Yes | Outreach summary |
| GET | `/api/outreach/pipeline` | Yes | Outreach pipeline |
| GET | `/api/seo/meta` | Yes | SEO meta descriptions |
| GET | `/api/seo/cities` | Yes | City landing pages |
| GET | `/api/seo/blog` | Yes | Blog posts (Hebrew) |
| GET | `/api/seo/images` | Yes | Adobe Firefly image prompts |
| GET | `/api/admin/status` | Yes | Business config + DB counts |
| GET | `/api/admin/usage` | Yes | Today's activity counts |
| POST | `/api/lead_ops/discover` | Yes | Run acquisition pipeline |
| POST | `/api/lead_ops/inbound` | Yes | Process inbound lead |
| POST | `/api/lead_ops/website` | Yes | Website growth analysis |
| GET | `/api/lead_ops/queue` | Yes | Current work queue |
| GET/POST | `/api/lead_ops/discovery_plan` | Yes | Source strategy — no DB |
| POST | `/api/lead_ops/draft` | Yes | Draft outreach message |
| GET | `/api/lead_ops/status` | Yes | Summary counts |
| GET | `/api/lead_ops/brief/<id>` | Yes | AI lead briefing |
| POST | `/api/lead_ops/batch_score` | Yes | Batch score leads |
| POST | `/api/lead_ops/execute/<id>` | Yes | Execute approved outreach |
| POST | `/api/telegram/webhook` | Token | Inbound Telegram + callbacks |
| POST | `/api/claude/preview` | Yes | Preview sensitive action |
| POST | `/api/claude/dispatch` | Yes | Dispatch via Claude bridge |
| GET | `/api/claude/tasks/<id>` | Yes | Task status |
| GET/POST | `/api/gpt/*` | Yes | GPT connector |
| POST | `/api/mcp` | No | MCP endpoint |

---

## Governance Rules

> Source of truth: `docs/ashbelos-governance.md`. Rules below are a summary.

1. Business context locked to Ashbal Aluminum only
2. Approved external channel: **Telegram only** (Wave One)
3. WhatsApp execution route exists but must not be expanded
4. Sensitive action flow: **Intent → Preview → Approval → Execute → Audit Log**
5. Business logic stays native to AshbelOS (lead scoring, revenue logic, Israeli adaptation)
6. Fallback paths must work without external bridges

---

## Learning Feedback (Phase 17+)

`skills/learning_skills.py` — stateless pattern tracking via MemoryStore.

MemoryStore keys:
- `global.template_outcomes` — approval/rejection of outreach drafts
- `global.source_strategies` — lead source outcomes (qualifies after 3+ runs)
- `global.agent_metrics` — per-agent success/latency
- `global.lead_conversion_rates` — conversion by score bucket
- `global.model_routing_overrides` — performance-based model routing

---

## How to Add a New Agent

```python
# 1. Create file: agents/departments/{dept}/{name}_agent.py
class MyAgent(BaseAgent):
    agent_id   = "builtin_my_agent_v1"
    name       = "My Agent"
    department = "sales"
    version    = 1

    def can_handle(self, task_type: str, action: str) -> bool:
        return task_type == "sales" and action == "my_action"

    def execute(self, task: TaskModel) -> ExecutionResult:
        try:
            local = self._local_compute(task)
            if local: return local
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

## Token Optimization Rules
1. **Local-first:** check `_local_compute()` before any AI call
2. **Model routing:** Haiku→routing/classify, Sonnet→content/draft, Opus→strategy
3. **Prompt caching:** pass `use_cache=True` to `_ai_call()` for repeated system prompts
4. **Batch:** use `model_router.call_batch(prompts)` for multi-lead processing
5. **Log costs:** `cost_tracker.flush_to_session_log(agent_name)` after AI calls

---

## Testing Patterns

```bash
# Run all tests (246 passing as of Phase 21)
PYTHONPATH=. python -m pytest tests/ -q

# Must be green before every commit
```

---

## Deployment Checklist
- [ ] pytest 246/246 green
- [ ] `GET /api/health` → 200 `{"db": true}`
- [ ] `POST /api/command {"command":"הצג לידים"}` → 200
- [ ] Railway env vars: OS_API_KEY, DATABASE_URL, TELEGRAM_BOT_TOKEN,
      TELEGRAM_CHAT_ID, WEBHOOK_VERIFY_TOKEN, ANTHROPIC_API_KEY
- [ ] push to master → Railway auto-deploys

---

## Efficient Execution Rules

- Use `CLAUDE.md` as primary source of truth. This skill file is a quick-start reference only.
- Prefer current system structure (agents, routes, hooks, docs) over re-analysis.
- Use metadata-first approach for external capabilities.
- Runtime completion requires real proof: working routes, active hooks, approval flow, execution path, deploy verification.
- Natural language system-change requests require preview and approval before execution.
- Block any change that creates duplication, replaces working flows, or bypasses governance.
