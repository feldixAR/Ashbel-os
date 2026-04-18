# AshbelOS — Agents, Skills & Orchestration

> Source of truth for capability architecture, agent registry, skill contracts, and orchestration flow.
> **Updated: 2026-04-18 — Scope Reset v2.0**

---

## Architecture

```
User Goal / Input
      ↓
Intent Parser (orchestration/intent_parser.py)
      ↓
Orchestrator (orchestration/orchestrator.py)
      ↓
Task Manager (orchestration/task_manager.py)  ← parallel_dispatch() for compound tasks
      ↓
Executor (_HANDLERS dict in services/execution/executor.py)
      ↓
Agents (agents/departments/**) → Skills (skills/**) → Engines (engines/**)
      ↓
Storage (PostgreSQL) + Memory (MemoryStore) + Events (EventBus)
```

---

## Agent Registry

Location: `agents/base/agent_registry.py`
Bootstrap: `agent_registry.bootstrap()` registers all builtin agents on app startup.

### Registered Agents (v7.0+)

| Agent | Department | Task Types / Actions | File |
|-------|-----------|---------------------|------|
| LeadAcquisitionAgent | sales | acquisition/* | `agents/departments/sales/lead_acquisition_agent.py` |
| LeadQualifierAgent | sales | qualification/* | `agents/departments/sales/lead_qualifier.py` |
| MessagingAgent | sales | messaging/* | `agents/departments/sales/messaging_agent.py` |
| FollowUpAgent | sales | followup/*, outreach/followup_queue | `agents/departments/sales/followup_agent.py` |
| ChannelStrategyAgent | sales | channel/* | `agents/departments/sales/channel_strategy_agent.py` |
| MarketingStrategyAgent | sales | marketing/* | `agents/departments/sales/marketing_strategy_agent.py` |
| CEOAgent | executive | strategy/*, revenue/*, agent_build/* | `agents/departments/executive/ceo_agent.py` |
| ChiefOfStaffAgent | executive | executive/* | `agents/departments/executive/chief_of_staff_agent.py` |
| ReportingAgent | executive | reporting/* | `agents/departments/executive/reporting_agent.py` |
| SEOAgent | executive | seo/* | `agents/departments/executive/seo_agent.py` |
| BuildManagerAgent | executive | development/* | `agents/departments/executive/build_manager_agent.py` |
| CodeBuilderAgent | executive | code_build/* | `agents/departments/executive/code_builder_agent.py` |
| ExecutiveAssistantAgent | executive | assistant/* | `agents/departments/executive/executive_assistant_agent.py` |
| GitHubWriterAgent | executive | github/* | `agents/departments/executive/github_writer_agent.py` |
| MaintenanceAgent | executive | maintenance/* | `agents/departments/executive/maintenance_agent.py` |
| SalesAssistantAgent | executive | sales_assist/* | `agents/departments/executive/sales_assistant_agent.py` |
| GenericTaskAgent | generic | fallback | `agents/departments/generic/task_agent.py` |

### Agent Contract (mandatory fields)
Every agent must:
- Set `agent_id`, `name`, `department`, `version` class attributes
- Implement `can_handle(task_type, action) -> bool` — deterministic, no I/O
- Implement `execute(task) -> ExecutionResult` — must never raise
- Catch all exceptions internally, return `ExecutionResult(success=False, ...)` on failure
- Log at INFO level on start, ERROR on failure
- Support `_local_compute()` override to avoid AI calls when possible

---

## Agent Contracts

### CEOAgent — Strategic Orchestrator
**Role:** Accepts high-level business goals. Decomposes into subtasks. Dispatches specialist agents in parallel. Aggregates outputs. Sends for approval when needed.
**Inputs:** business goal, command string, context
**Outputs:** unified strategic summary, approval requests, task dispatch results
**Key actions:** `complex_reasoning`, `compound_analysis`, `revenue_insights`, `bottleneck_analysis`, `next_best_action`
**Skills:** `revenue_engine`, `learning_engine`, parallel_dispatch
**Approval gate:** any execution (outreach, system change) requires approval
**Audit:** logs to `ActivityModel` on every compound execution

### LeadAcquisitionAgent
**Role:** Discovers, processes, deduplicates, enriches, and scores leads from any source.
**Inputs:** goal string, signals list, document content, inbound contact
**Outputs:** work_queue (scored leads), discovery_plan, recommended_source
**Key actions:** `discover_leads`, `process_inbound`, `parse_document`, `lead_ops_queue`
**Skills:** `source_discovery`, `lead_intelligence`, `document_intelligence`
**Limits:** does not send outreach; hands off to MessagingAgent/FollowUpAgent

### FollowUpAgent
**Role:** Manages follow-up scheduling, queue, and batch draft generation.
**Inputs:** lead_id, days_ahead, batch limit
**Outputs:** follow-up queue, scheduled activity log, batch drafts
**Key actions:** `followup_queue`, `schedule_followup`, `batch_followup`
**Skills:** `outreach_intelligence`, `learning_skills.get_best_template()`
**Learning hook:** always uses `get_best_template("follow_up", segment, channel)` before falling back to default

### ChannelStrategyAgent
**Role:** Selects best outreach channel for a lead based on profile, segment, history, and learning data.
**Inputs:** lead dict, business profile
**Outputs:** recommended_channel, channel_status (active/readiness/blocked), alternative channels
**Key actions:** `select_channel`, `channel_status`
**Skills:** `outreach_intelligence.choose_channel()`, `learning_skills`, `services/channels/channel_router.py`
**Rules:** always returns manual_send as fallback; respects channel readiness status

### MarketingStrategyAgent
**Role:** Generates marketing recommendations, campaign ideas, content calendar, seasonal offers.
**Inputs:** business profile, learning signals, competitor context
**Outputs:** weekly recommendations, campaign drafts, content calendar
**Key actions:** `weekly_recommendations`, `campaign_draft`, `marketing_analysis`
**Skills:** `engines/marketing_engine.py`, business profile context

### SEOAgent
**Role:** Analyzes business website, detects gaps, generates SEO content.
**Inputs:** site_url (from business profile), target keywords, existing pages
**Outputs:** gap analysis, content recommendations, city pages, blog posts, meta tags
**Key actions:** `analyze_website`, `generate_seo_content`, `seo_report`
**Skills:** `engines/seo_engine.py`, `skills/website_growth.py`
**Readiness:** generates content; actual website updates blocked until CMS credentials

### ReportingAgent
**Role:** Generates daily, weekly, performance, and KPI reports.
**Inputs:** date range, report type
**Outputs:** formatted report text, KPI dict
**Key actions:** `generate_report`, `daily_summary`, `weekly_report`, `performance_report`, `kpi_snapshot`

### MessagingAgent
**Role:** Drafts, previews, and routes outreach messages through the approval flow.
**Inputs:** lead_id, channel, template_type, context
**Outputs:** draft message, approval request
**Key actions:** `draft_message`, `draft_meeting`, routing through approval gate

---

## Skills Inventory

Location: `skills/`

| Module | Key Functions | Used By |
|--------|--------------|---------|
| `source_discovery.py` | `discover_sources()`, `rank_sources()` | lead_acquisition_engine |
| `lead_intelligence.py` | `score_lead()`, `enrich_lead()`, `next_action()` | orchestrator, executor |
| `outreach_intelligence.py` | `draft_first_contact()`, `draft_followup()`, `choose_channel()` | lead_ops/draft, briefing |
| `israeli_context.py` | `classify_segment()`, `get_local_channels()` | discovery, outreach |
| `workflow_skills.py` | `build_workflow()`, `select_next_step()` | task_manager |
| `learning_skills.py` | `record_template_outcome()`, `get_best_template()`, `promote_model()` | approvals, agents |
| `document_intelligence.py` | `parse_document()`, `classify_records()` | intake route |
| `website_growth.py` | `analyze_website()`, `suggest_content()` | seo engine |

---

## Channel Services

Location: `services/channels/`

| Module | Role | Status |
|--------|------|--------|
| `channel_base.py` | Base class, ChannelResult dataclass | Active |
| `channel_router.py` | Routes to correct channel, returns status | Active |
| `manual_send.py` | Generates manual send instructions + copy link | Active (full) |
| `email_channel.py` | Email draft, MIME build, preview | Readiness only — needs SMTP credentials |
| `whatsapp_readiness.py` | WhatsApp deep link + draft | Readiness only — needs Meta credentials |
| `meta_readiness.py` | Facebook/Instagram content draft | Readiness only — needs Meta Business credentials |
| `linkedin_readiness.py` | LinkedIn compliant content draft | Readiness only — needs LinkedIn API credentials |

---

## Orchestration Dispatch Flow

### Goal → Capability Selection

```
POST /api/command {"command": "..."}
  → intent_parser.parse_intent(command)
  → orchestrator.dispatch(intent, context)
  → task_manager.create_task(type, action, payload)
  → executor._HANDLERS[action](task)  OR  agent_registry.find(type, action).execute(task)
  → result stored in tasks table
```

### Parallel Compound Dispatch (CEOAgent)

```
compound_analysis command
  → CEOAgent._compound_analysis(task)
  → parallel_dispatch([revenue_insights, bottleneck_analysis, next_best_action])
  → merge results → unified output
```

### Channel Dispatch Flow

```
Draft outreach
  → channel_router.select(lead, profile)  → channel + status
  → channel.draft(lead, message)          → ChannelResult
  → if status == readiness_only:
      manual_send.generate_instructions() → operator sends manually
  → approval gate → audit log
```
