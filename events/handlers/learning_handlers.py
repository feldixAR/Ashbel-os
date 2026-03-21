"""
Learning event handlers.

Triggered by: PATTERN_DETECTED, PROMPT_OPTIMIZED, ROUTING_MAP_UPDATED

Responsibilities:
  - Persist detected patterns to memory for future use
  - Apply prompt optimisations to the memory store
  - Apply routing map updates so the model router picks them up immediately
  - Maintain a changelog of all learning events
"""

import logging
import datetime
from memory.memory_store import MemoryStore

log = logging.getLogger(__name__)


def on_pattern_detected(event_type: str, payload: dict, meta: dict) -> None:
    """
    The learning engine detected a statistically significant pattern.
    Stores the pattern and appends it to the changelog.
    """
    pattern_key  = payload.get("pattern_key", "unknown")
    pattern_value = payload.get("pattern_value")
    confidence   = payload.get("confidence", 0.0)
    source       = payload.get("source", "learning_engine")

    log.info(
        f"[LearningHandler] pattern detected: {pattern_key} "
        f"value={pattern_value} confidence={confidence:.2f}"
    )

    # Store the pattern
    MemoryStore.write("patterns", pattern_key, {
        "value":      pattern_value,
        "confidence": confidence,
        "source":     source,
        "detected_at": datetime.datetime.utcnow().isoformat(),
    })

    # Append to learning changelog
    _append_changelog("pattern_detected", {
        "key":        pattern_key,
        "value":      pattern_value,
        "confidence": confidence,
    })


def on_prompt_optimized(event_type: str, payload: dict, meta: dict) -> None:
    """
    A system prompt was improved by the learning engine.
    Stores the optimised prompt so the agent factory can apply it on next run.
    """
    agent_id      = payload.get("agent_id")
    agent_name    = payload.get("agent_name", "unknown")
    new_prompt    = payload.get("new_prompt", "")
    improvement   = payload.get("improvement_summary", "")
    trigger_metric = payload.get("trigger_metric", "")

    log.info(
        f"[LearningHandler] prompt optimised: {agent_name} "
        f"(id={agent_id}) trigger={trigger_metric}"
    )

    if agent_id and new_prompt:
        MemoryStore.set_agent(agent_id, "pending_prompt_upgrade", {
            "new_prompt":   new_prompt,
            "improvement":  improvement,
            "created_at":   datetime.datetime.utcnow().isoformat(),
        })

    _append_changelog("prompt_optimized", {
        "agent_id":   agent_id,
        "agent_name": agent_name,
        "trigger":    trigger_metric,
    })


def on_routing_map_updated(event_type: str, payload: dict, meta: dict) -> None:
    """
    The model routing map was updated by the learning engine.
    Applies overrides to MemoryStore so ModelRouter picks them up immediately.
    """
    updates  = payload.get("updates", {})   # {task_type: model_key}
    reason   = payload.get("reason", "")

    if not updates:
        log.debug("[LearningHandler] routing_map_updated with no changes")
        return

    log.info(
        f"[LearningHandler] routing map updated: "
        f"{len(updates)} change(s) — {reason}"
    )

    for task_type, model_key in updates.items():
        MemoryStore.set_routing_override(task_type, model_key)
        log.info(f"[LearningHandler] routing override: {task_type} → {model_key}")

    _append_changelog("routing_map_updated", {
        "updates": updates,
        "reason":  reason,
    })


# ── Internal helpers ──────────────────────────────────────────────────────────

def _append_changelog(event: str, details: dict) -> None:
    changelog = MemoryStore.read("global", "learning_changelog", [])
    changelog.append({
        "event":   event,
        "details": details,
        "ts":      datetime.datetime.utcnow().isoformat(),
    })
    # Keep only last 200 entries
    if len(changelog) > 200:
        changelog = changelog[-200:]
    MemoryStore.write("global", "learning_changelog", changelog)
