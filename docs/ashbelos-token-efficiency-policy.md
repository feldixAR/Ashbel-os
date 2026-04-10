# AshbelOS Token Efficiency Policy

> **Source of truth for all token optimization decisions.**
> CLAUDE.md §Token Discipline Policy is an adapter of this document. If conflict exists, this document wins until CLAUDE.md is corrected.

---

## Core Rule

Always optimize for maximum token efficiency without reducing code quality, correctness, safety, or implementation clarity.

---

## Required Behavior

- Stay in execution mode once scope is approved.
- Start from current repo state only.
- Do not restart broad analysis unless a true blocker requires it.
- Do not recap old context that is already established.
- Do not reopen closed architecture decisions.
- Do not ask for confirmation for normal repo work.
- Do not create parallel systems when existing modules can be extended.
- Prefer direct implementation over long investigation.

---

## Repo Reading Discipline

- Read only files required for the current task or phase.
- Do not rescan the whole repo unless strictly necessary.
- Do not reread files that were already verified unless they changed or are directly relevant.
- Prefer targeted inspection over broad exploration.

---

## Tool and Agent Discipline

- Do not launch broad subagents unless strictly necessary.
- Use the smallest effective tool/action path.
- Avoid repeated scans, repeated status checks, and repeated summaries.
- Prefer one focused pass over multiple exploratory passes.

---

## Output Discipline

- Return compact status only unless more detail is explicitly requested.
- Keep updates short and execution-first.
- Mark completed checklist items with [x].
- Report only what changed, what is in progress, and true blockers.

---

## Scope Discipline

- Work in controlled phases.
- Complete the current approved phase before expanding scope.
- Do not mix unrelated batches in one run unless explicitly requested.
- Stop only for:
  - true external blockers
  - missing credentials
  - destructive risk
  - deployment/runtime actions outside the repo

---

## Architectural Discipline

- Preserve approved business logic, sensitive flow, auditability, fallback behavior, and AshbelOS as the independent business core.
- No token-saving shortcut may weaken architecture or correctness.

---

## Runtime Token Optimization Rules

These rules apply to all agent and engine code:

### 1. Local-First
Check `_local_compute()` before any AI call. Pure Python checks (timing, quota, compliance) must return a result before any model is invoked.

```python
local = self._local_compute(task)
if local:
    return local
```

### 2. Model Routing
Route to the cheapest model that can handle the task:

| Model | ID | Use cases |
|-------|----|-----------|
| Haiku | `claude-haiku-4-5-20251001` | Classification, routing, CRM lookups, scoring |
| Sonnet | `claude-sonnet-4-6` | Drafting, outreach content, sales analysis |
| Opus | `claude-opus-4-6` | Strategy, complex reasoning, CEO/Chief of Staff decisions |

### 3. Prompt Caching
Pass `use_cache=True` to `_ai_call()` for system prompts that repeat across calls.
The model router wraps system prompts in `cache_control: {"type": "ephemeral"}`.

### 4. Batch Processing
Use `model_router.call_batch(task_type, system_prompt, user_prompts, ...)` for multi-lead processing. Batches of 10.

### 5. Session Cost Logging
After every AI call, flush token usage:
```python
cost_tracker.flush_to_session_log(agent_name)
```
Logs are written to `memory/sessions/YYYY-MM-DD.md`.

---

## Priority Order

1. Safety and correctness
2. Approved architecture and policy compliance
3. Token efficiency
4. Execution speed
5. Extra explanation
