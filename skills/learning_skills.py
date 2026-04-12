"""
learning_skills.py — Stateless learning and pattern tracking via MemoryStore.

Responsibilities:
  - Track best-performing outreach templates by segment/channel
  - Record successful lead source strategies by goal type
  - Update agent performance patterns (success/failure rates)
  - Recall learned patterns for scoring, routing, and source selection

All functions are pure/stateless — they accept inputs, interact with MemoryStore,
and return structured results. No side-effects beyond MemoryStore writes.
"""
from __future__ import annotations

import logging
from typing import Any, Optional

log = logging.getLogger(__name__)

# Lazy import — MemoryStore requires DB; avoid import-time errors in tests
def _store():
    from memory.memory_store import MemoryStore
    return MemoryStore


# ── Template learning ──────────────────────────────────────────────────────────

def record_template_outcome(
    template_type: str,
    template_text: str,
    outcome: str,          # "reply" | "meeting" | "ignored" | "rejected"
    segment: Optional[str] = None,
    channel: Optional[str] = None,
) -> dict:
    """
    Record the outcome of a sent outreach template.
    Promotes template to 'best' if outcome is positive (reply/meeting).
    Returns: {"recorded": bool, "promoted": bool}
    """
    ms = _store()
    key = _template_key(template_type, segment, channel)
    positive = outcome in ("reply", "meeting")

    existing = ms.read("messaging", f"stats_{key}", {})
    existing["total"] = existing.get("total", 0) + 1
    existing[outcome] = existing.get(outcome, 0) + 1
    ms.write("messaging", f"stats_{key}", existing, updated_by="learning_skills")

    promoted = False
    if positive:
        current_best = ms.read("messaging", f"best_{key}")
        # Promote if no best exists, or this template has better rate
        if not current_best or _is_better_template(existing):
            ms.write("messaging", f"best_{key}", template_text, updated_by="learning_skills")
            promoted = True

    log.debug("Template outcome recorded: key=%s outcome=%s promoted=%s", key, outcome, promoted)
    return {"recorded": True, "promoted": promoted}


def get_best_template(
    template_type: str,
    segment: Optional[str] = None,
    channel: Optional[str] = None,
) -> Optional[str]:
    """
    Return best-performing template for the given type/segment/channel.
    Falls back: segment+channel → type-only → None.
    """
    ms = _store()
    if segment and channel:
        result = ms.read("messaging", f"best_{_template_key(template_type, segment, channel)}")
        if result:
            return result
    if segment:
        result = ms.read("messaging", f"best_{_template_key(template_type, segment, None)}")
        if result:
            return result
    return ms.read("messaging", f"best_{template_type}")


def _template_key(template_type: str, segment: Optional[str], channel: Optional[str]) -> str:
    parts = [template_type]
    if segment:
        parts.append(segment.lower().replace(" ", "_"))
    if channel:
        parts.append(channel.lower())
    return "_".join(parts)


def _is_better_template(stats: dict) -> bool:
    """Return True if the stats indicate a above-threshold success rate."""
    total = stats.get("total", 0)
    if total < 2:
        return True  # Not enough data — allow promotion
    positive = stats.get("reply", 0) + stats.get("meeting", 0)
    return (positive / total) >= 0.3


# ── Source strategy learning ───────────────────────────────────────────────────

def record_source_outcome(
    source_type: str,   # e.g. "google_maps", "manual", "inbound", "referral"
    goal_type: str,     # e.g. "residential", "commercial", "renovation"
    leads_found: int,
    leads_qualified: int,
) -> dict:
    """
    Record how a source performed for a goal type.
    Returns: {"recorded": bool, "best_source": str|None}
    """
    ms = _store()
    key = f"source_{goal_type}"
    existing: dict = ms.read("leads", key, {})

    src = existing.get(source_type, {"found": 0, "qualified": 0, "runs": 0})
    src["found"] += leads_found
    src["qualified"] += leads_qualified
    src["runs"] = src.get("runs", 0) + 1
    existing[source_type] = src
    ms.write("leads", key, existing, updated_by="learning_skills")

    # Determine current best source for this goal type
    best = _best_source(existing)
    ms.write("leads", f"best_source_{goal_type}", best, updated_by="learning_skills")

    return {"recorded": True, "best_source": best}


def get_best_source(goal_type: str) -> Optional[str]:
    """Return the historically best lead source for a given goal type."""
    return _store().read("leads", f"best_source_{goal_type}")


def get_source_stats(goal_type: str) -> dict:
    """Return full per-source stats for a goal type."""
    return _store().read("leads", f"source_{goal_type}", {})


def _best_source(source_map: dict) -> Optional[str]:
    """Pick source with highest qualification rate (min 3 runs)."""
    best_src, best_rate = None, -1.0
    for src, stats in source_map.items():
        runs = stats.get("runs", 0)
        if runs < 3:
            continue
        found = stats.get("found", 0) or 1
        rate = stats.get("qualified", 0) / found
        if rate > best_rate:
            best_rate, best_src = rate, src
    return best_src


# ── Agent performance tracking ────────────────────────────────────────────────

def record_agent_outcome(
    agent_id: str,
    action_type: str,
    success: bool,
    latency_ms: Optional[int] = None,
) -> dict:
    """
    Track success/failure for an agent action.
    Returns updated aggregate stats.
    """
    ms = _store()
    key = f"action_{action_type}"
    stats: dict = ms.read(f"agent:{agent_id}", key, {
        "success": 0, "failure": 0, "total": 0, "avg_latency_ms": None
    })

    stats["total"] += 1
    if success:
        stats["success"] += 1
    else:
        stats["failure"] += 1

    if latency_ms is not None:
        prev_avg = stats.get("avg_latency_ms") or latency_ms
        stats["avg_latency_ms"] = int((prev_avg + latency_ms) / 2)

    ms.write(f"agent:{agent_id}", key, stats, updated_by="learning_skills")

    # Update global agent performance summary
    _update_global_agent_summary(agent_id, stats)

    return stats


def get_agent_stats(agent_id: str, action_type: Optional[str] = None) -> dict:
    """Return performance stats for an agent, optionally filtered by action type."""
    ms = _store()
    if action_type:
        return ms.read(f"agent:{agent_id}", f"action_{action_type}", {})
    return ms.list_namespace(f"agent:{agent_id}")


def _update_global_agent_summary(agent_id: str, action_stats: dict) -> None:
    ms = _store()
    summary: dict = ms.read("global", "agent_summary", {})
    total = action_stats.get("total", 0)
    success = action_stats.get("success", 0)
    rate = round(success / total, 3) if total else 0.0
    summary[agent_id] = {"total": total, "success": success, "success_rate": rate}
    ms.write("global", "agent_summary", summary, updated_by="learning_skills")


# ── Scoring pattern learning ───────────────────────────────────────────────────

def record_lead_conversion(
    lead_id: str,
    segment: Optional[str],
    source_type: Optional[str],
    score_at_outreach: int,
    converted: bool,
) -> dict:
    """
    Record whether a scored lead ultimately converted.
    Helps calibrate scoring thresholds over time.
    """
    ms = _store()
    bucket = _score_bucket(score_at_outreach)
    key = f"conversion_bucket_{bucket}"
    stats: dict = ms.read("leads", key, {"converted": 0, "total": 0})
    stats["total"] += 1
    if converted:
        stats["converted"] += 1
    ms.write("leads", key, stats, updated_by="learning_skills")

    # Per-segment conversion tracking
    if segment:
        seg_key = f"conversion_seg_{segment.lower()}"
        seg: dict = ms.read("leads", seg_key, {"converted": 0, "total": 0})
        seg["total"] += 1
        if converted:
            seg["converted"] += 1
        ms.write("leads", seg_key, seg, updated_by="learning_skills")

    return {"bucket": bucket, "stats": stats}


def get_conversion_stats() -> dict:
    """Return conversion rates across score buckets."""
    ms = _store()
    result = {}
    for bucket in ("low", "medium", "high", "hot"):
        s = ms.read("leads", f"conversion_bucket_{bucket}", {})
        total = s.get("total", 0)
        conv = s.get("converted", 0)
        result[bucket] = {
            "total": total,
            "converted": conv,
            "rate": round(conv / total, 3) if total else None,
        }
    return result


def _score_bucket(score: int) -> str:
    if score >= 80:
        return "hot"
    if score >= 60:
        return "high"
    if score >= 40:
        return "medium"
    return "low"


# ── Routing recommendations ────────────────────────────────────────────────────

def recommend_model(task_type: str, default: str = "haiku") -> str:
    """
    Return the recommended Claude model for a task type based on routing overrides.
    Falls back to default if no override is set.
    """
    override = _store().get_routing_override(task_type)
    return override or default


def promote_model(task_type: str, model_key: str, reason: str = "") -> None:
    """Set a routing override — called after observing performance improvement."""
    _store().set_routing_override(task_type, model_key)
    if reason:
        _store().write(
            "routing", f"reason_{task_type}", reason, updated_by="learning_skills"
        )
