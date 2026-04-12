# AshbelOS — Agents, Skills & Orchestration

> Source of truth for capability architecture, agent registry, skill contracts, and orchestration flow.

---

## Architecture

```
User Goal / Input
      ↓
Intent Parser (orchestration/intent_parser.py)
      ↓
Orchestrator (orchestration/orchestrator.py)
      ↓
Task Manager (orchestration/task_manager.py)
      ↓
Executor (_HANDLERS dict in services/execution/executor.py)
      ↓
Engines / Agents / Skills
      ↓
Storage (PostgreSQL) + Memory (MemoryStore) + Events (EventBus)
```

---

## Agent Registry

Location: `agents/registry.py`
Agents are registered with: id, name, department, role, capabilities, model_preference.

| Agent ID | Department | Key Capabilities |
|----------|-----------|-----------------|
| lead_acquisition_agent | sales | discover_leads, batch_classify, inbound_processing, follow_up_proposals |
| (others registered in registry) | various | see registry.py |

### Agent State Visibility
- `last_active_at`: timestamp of last task execution
- `tasks_done`: cumulative task count
- `active_version`: current agent version
- Status derived: `last_active_at` within 24h → active, else idle

---

## Skills Inventory

Location: `skills/`

| Module | Key Functions | Used By |
|--------|--------------|---------|
| `source_discovery.py` | `discover_sources()`, `rank_sources()` | lead_acquisition_engine |
| `lead_intelligence.py` | `score_lead()`, `enrich_lead()`, `next_action()` | orchestrator, executor |
| `outreach_intelligence.py` | `draft_first_contact()`, `draft_followup()`, `draft_meeting_request()` | lead_ops/draft, briefing |
| `israeli_context.py` | `classify_segment()`, `get_local_channels()` | discovery, outreach |
| `workflow_skills.py` | `build_workflow()`, `select_next_step()` | task_manager |
| `learning_skills.py` | `track_template_outcome()`, `track_source_strategy()` | approvals, lead_ops |
| `document_intelligence.py` | `parse_document()`, `classify_records()` | intake route |
| `website_growth.py` | `analyze_website()`, `suggest_content()` | seo engine |

---

## Orchestration Dispatch Flow

### Goal → Capability Selection

```
POST /api/command {"command": "..."} 
  → intent_parser.parse_intent(command)
  → orchestrator.dispatch(intent, context)
  → task_manager.create_task(type, action, payload)
  → executor._HANDLERS[action](payload)
  → result stored in tasks table
```

### Direct Skill Routes

```
POST /api/lead_ops/discover   → lead_acquisition_engine.run_acquisition()
POST /api/lead_ops/draft      → outreach_intelligence.draft_*()
POST /api/lead_ops/inbound    → lead_acquisition_engine.process_inbound()
POST /api/lead_ops/batch_score → lead_intelligence.score_lead() × N
GET  /api/lead_ops/brief/<id> → _build_lead_briefing() via model_router
```

---

## Sensitive Action Policy

All sensitive actions follow: Intent → Preview → Approval → Execute → Audit Log

- `POST /api/approvals/<id>/approve` executes approved actions
- All outreach drafts: `requires_approval: True`
- System changes: branch created, plan stored in MemoryStore
- No sensitive action bypasses the approval gate

---

## Capability Registry (Orchestration Selection)

The executor `_HANDLERS` dict is the runtime capability registry:
- Location: `services/execution/executor.py` (module-level, after all `_handle_*` functions)
- Keys: action string identifiers
- Values: handler functions

To add a capability: implement `_handle_<action>()`, add to `_HANDLERS`.

---

## Learning Feedback

Outcomes feed back via `skills/learning_skills.py`:
- Template outcome: approval/rejection of outreach → adjusts template weights
- Source strategy: lead source outcomes → qualifies sources after 3+ runs
- Agent success/latency: tracks per-agent performance
- Lead conversion: by score bucket → refines scoring
- Model routing: performance → overrides default model per action type

MemoryStore keys:
- `global.template_outcomes`
- `global.source_strategies`
- `global.agent_metrics`
- `global.lead_conversion_rates`
- `global.model_routing_overrides`
