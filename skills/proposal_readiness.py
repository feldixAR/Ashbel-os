"""Proposal readiness rules for Ashbel Aluminum leads."""
from __future__ import annotations

import datetime as _dt
from typing import Any


def evaluate(lead: dict[str, Any]) -> dict[str, Any]:
    """Return proposal readiness flags without side effects."""
    data = {k: _clean(v) for k, v in lead.items()}
    notes = " ".join([data.get("notes", ""), data.get("text", ""), data.get("description", "")]).lower()
    missing = {
        "missing_photos": not _has_flag_or_text(data, notes, "photos", ["תמונה", "תמונות", "photo", "photos"]),
        "missing_plans": not _has_flag_or_text(data, notes, "plans", ["תכנית", "תוכניות", "תכניות", "plan", "plans"]),
        "missing_measurements": not _has_flag_or_text(data, notes, "measurements", ["מידות", "מדידה", "measure", "measurements"]),
        "missing_address": not bool(data.get("address") or data.get("city")),
        "missing_decision_maker": not bool(data.get("decision_maker") or data.get("name")),
        "missing_budget": not bool(data.get("estimated_value") or data.get("budget")),
        "missing_project_stage": not bool(data.get("project_stage")),
    }
    ready = not any(missing.values())
    followup = _dt.datetime.now(_dt.timezone.utc) + _dt.timedelta(days=1 if not ready else 3)
    return {
        "ready_for_proposal": ready,
        **missing,
        "proposal_followup_date": followup.date().isoformat(),
        "proposal_metadata": {
            "ready": ready,
            "missing": [key for key, value in missing.items() if value],
            "source": "proposal_readiness.evaluate",
        },
    }


def _clean(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _has_flag_or_text(data: dict[str, str], notes: str, field: str, keywords: list[str]) -> bool:
    explicit = data.get(field) or data.get(f"has_{field}")
    missing_explicit = data.get(f"missing_{field}")
    if missing_explicit:
        return missing_explicit.lower() in ("no", "false", "0", "לא", "קיים", "יש")
    if explicit:
        return explicit.lower() in ("yes", "true", "1", "יש", "קיים", "קיימות")
    return any(keyword.lower() in notes for keyword in keywords)
