# AshbelOS — Agent Contracts

> **Phase 12 update:** Six skill modules added under `skills/`. Skills are stateless, contract-based units. Engines orchestrate skills. Agents use skills for sub-tasks.
> **Phase 13 update:** `LeadAcquisitionAgent` added — handles all `acquisition/*` actions via registry. Acquisition actions removed from `_HANDLERS`. Includes Haiku batch signal pre-filter, Sonnet inbound draft (prompt cache), local-first empty-signal fast path.

> Derived from `agents/base/base_agent.py`, `agents/base/agent_registry.py`, `CLAUDE.md`, and `SKILL.md`.
> Do not invent new architecture here — this reflects code reality.

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
| ChiefOfStaffAgent | `executive/chief_of_staff_agent.py` | executive | plan_action | Opus (strategy), Haiku (classify) |
| MaintenanceAgent | `executive/maintenance_agent.py` | executive | maintenance_report | Sonnet |
| GenericTaskAgent | `generic/task_agent.py` | * | * | Sonnet (fallback) |

---

## Execution Contract

1. `task_manager.dispatch(task)` owns the full lifecycle — start → execute → complete/fail
2. Orchestrator must NOT call `mark_completed` or `mark_failed` directly
3. `_HANDLERS` in `executor.py` is module-level, defined after all `_handle_*` functions
4. `OrchestratorResult` is a `@dataclass` — access `.message`, `.intent`, `.success` (not dict keys)

---

## Local-First Contract

Every agent must check `_local_compute(task)` before any AI call:

```python
local = self._local_compute(task)
if local:
    return local
# AI call only if local returns None
result = self._ai_call(task_type, system_prompt, user_prompt, priority, use_cache)
```

`_local_compute()` returns `None` by default. Override to run pure Python checks (timing, quota, scoring).

---

## Token Routing Contract

Agents must select the cheapest model that can handle the task:

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

## Adding a New Agent

1. Create `agents/departments/{dept}/{name}_agent.py`
2. Implement `can_handle()` and `execute()`
3. Register in `agents/base/agent_registry.py:bootstrap()`
4. Add `Intent` in `orchestration/intent_parser.py`
5. Add to `_INTENT_TASK_MAP` in `orchestration/orchestrator.py`
6. Run `PYTHONPATH=. venv/Scripts/pytest tests/ -q` — all must pass
7. Commit
