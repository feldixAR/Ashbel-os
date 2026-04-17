# AshbelOS — Agent Contracts

> Reflects code reality through Phase 21 (v5.2).
> Source of truth: `CLAUDE.md`, `docs/AGENTS_SKILLS_ORCHESTRATION.md`.
> Do not invent new architecture here.

---

## Base Contract

Every agent extends `BaseAgent` and must implement:

```python
class MyAgent(BaseAgent):
    agent_id   = "builtin_my_agent_v1"   # unique, stable ID
    name       = "My Agent"
    department = "sales"                  # sales | executive | generic
    version    = 1

    def can_handle(self, task_type: str, action: str) -> bool:
        return task_type == "sales" and action == "my_action"

    def execute(self, task: TaskModel) -> ExecutionResult:
        ...
```

`agent_registry.py:bootstrap()` instantiates all agents at startup. The registry calls `can_handle()` to route tasks.

---

## Registered Agents

| Agent | File | task_type | action | Model |
|-------|------|-----------|--------|-------|
| LeadAcquisitionAgent | `sales/lead_acquisition_agent.py` | acquisition | * (all 4) | Haiku (classify/batch) + Sonnet (draft) |
| LeadQualifierAgent | `sales/lead_qualifier.py` | scoring | score_lead | Haiku |
| MessagingAgent | `sales/messaging_agent.py` | sales | generate_content | Sonnet |
| CEOAgent | `executive/ceo_agent.py` | strategy | ceo_decision | Opus |
| ChiefOfStaffAgent | `executive/chief_of_staff_agent.py` | executive | plan_action | Opus (strategy) + Haiku (classify) |
| MaintenanceAgent | `executive/maintenance_agent.py` | executive | maintenance_report | Sonnet |
| GenericTaskAgent | `generic/task_agent.py` | * | * | Sonnet (fallback) |

---

## Execution Contract

1. `task_manager.dispatch(task)` owns the full lifecycle — start → execute → complete/fail
2. Orchestrator must NOT call `mark_completed` or `mark_failed` directly
3. `_HANDLERS` in `executor.py` is module-level, defined after all `_handle_*` functions
4. `OrchestratorResult` is a `@dataclass` — access `.message`, `.intent`, `.success` (not dict keys)

---

## Executor Handlers (_HANDLERS)

Handlers added through Phase 21:

| Handler | Added | Purpose |
|---------|-------|---------|
| `_handle_parse_document` | Phase 16 | base64 content → `document_intelligence.parse_document()` → `process_inbound()` per record |
| `_handle_preview_system_change` | Phase 16 | Classify change intent → preview payload → `ApprovalModel` entry → Telegram card |

Natural language system-change requests flow: `SYSTEM_CHANGE` intent → `_handle_preview_system_change` → pending approval → on approval: create `feat/system-change-{id}` branch, store execution plan in `MemoryStore` at `global.pending_change_{id}`.

---

## Intent → Task Mapping

| Intent | task_type | action | Since |
|--------|-----------|--------|-------|
| DISCOVER_LEADS | acquisition | discover_leads | Phase 12 |
| PROCESS_INBOUND | acquisition | process_inbound | Phase 12 |
| WEBSITE_ANALYSIS | acquisition | website_analysis | Phase 12 |
| LEAD_OPS_QUEUE | acquisition | lead_ops_queue | Phase 12 |
| DOCUMENT_UPLOAD | acquisition | parse_document | Phase 16 |
| SYSTEM_CHANGE | executive | preview_system_change | Phase 16 |

---

## Local-First Contract

Every agent must check `_local_compute(task)` before any AI call:

```python
local = self._local_compute(task)
if local:
    return local
result = self._ai_call(task_type, system_prompt, user_prompt, priority, use_cache)
```

`_local_compute()` returns `None` by default. Override to run pure Python checks (timing, quota, scoring). Empty signals → plan only (0 tokens).

---

## Token Routing Contract

| Priority | Model | Use |
|----------|-------|-----|
| cheap | `claude-haiku-4-5-20251001` | Classification, routing, CRM lookups |
| balanced | `claude-sonnet-4-6` | Drafting, outreach, analysis |
| premium | `claude-opus-4-6` | Strategy, complex decisions |

Pass via `_ai_call(..., priority="cheap"|"balanced"|"premium")`.

---

## Cost Logging Contract

After every AI call, flush cost to session log:

```python
cost_tracker.flush_to_session_log(self.agent_id)
```

Writes to `memory/sessions/YYYY-MM-DD.md`.

---

## Approval Boundary

All outreach drafts have `requires_approval: True`. No sensitive action may execute without:
1. An `ApprovalModel` record in the DB
2. Explicit `approve` action via `/api/approvals/<id>` (REST) or Telegram inline keyboard
3. ActivityModel log entry on resolution
4. `LEAD_OUTREACH_SENT` event emitted on approval

UI-initiated approvals use `POST /api/approvals/create` (Phase 21) — same approval model, same audit trail.

---

## Learning Hooks (Phase 17+)

`LeadAcquisitionAgent` fires learning hooks after key outcomes:
- `learning_skills.track_template_outcome(template_id, approved)` — on outreach approval/denial
- `learning_skills.track_source_strategy(source, outcome)` — on lead conversion
- `learning_skills.track_agent_metrics(agent_id, latency, success)` — on every execution

`api/routes/approvals.py` records template outcome on outreach approval.
`skills/lead_intelligence.py` reads `global.model_routing_overrides` to adjust scoring weights per segment.

---

## Adding a New Agent

1. Create `agents/departments/{dept}/{name}_agent.py`
2. Implement `can_handle()` and `execute()`
3. Register in `agents/base/agent_registry.py:bootstrap()`
4. Add `Intent` in `orchestration/intent_parser.py`
5. Add to `_INTENT_TASK_MAP` in `orchestration/orchestrator.py`
6. Run `PYTHONPATH=. python -m pytest tests/ -q` — all must pass
7. Commit
