"""
services/growth/policy.py — Batch 9: Follow-up Lifecycle Policy.

Defines:
  - Valid lifecycle state transitions (FSM)
  - Per-channel follow-up delay rules
  - Helper to compute next_action_at from sent_at
  - Helper to evaluate whether a record is overdue for follow-up

Lifecycle states (lifecycle_status column):
    sent              — Telegram dispatch confirmed, waiting for operator action
    awaiting_response — Operator noted client was contacted, monitoring reply
    followup_due      — Follow-up deadline passed with no response
    followup_sent     — Follow-up asset generated + dispatched
    closed_won        — Deal confirmed
    closed_lost       — No interest / lost

State machine — valid transitions:
    sent               → awaiting_response | followup_due | closed_won | closed_lost
    awaiting_response  → followup_due | closed_won | closed_lost
    followup_due       → followup_sent | closed_won | closed_lost
    followup_sent      → awaiting_response | closed_won | closed_lost
    closed_won         → (terminal)
    closed_lost        → (terminal)
"""

from __future__ import annotations

import datetime
import logging
from typing import Optional

try:
    import pytz as _pytz
except ImportError:
    _pytz = None

log = logging.getLogger(__name__)
_IL_TZ = (_pytz.timezone("Asia/Jerusalem") if _pytz else __import__("datetime").timezone(__import__("datetime").timedelta(hours=3)))

# ── Follow-up delay rules (hours per channel) ──────────────────────────────────

FOLLOWUP_DELAY_HOURS: dict[str, int] = {
    "whatsapp": 48,
    "email":    72,
    "linkedin": 96,
    "internal": 0,    # outreach_briefs are internal — no follow-up timer
}

DEFAULT_FOLLOWUP_HOURS = 48

# ── Terminal states ────────────────────────────────────────────────────────────

TERMINAL_STATES = {"closed_won", "closed_lost"}

# ── Valid transitions FSM ──────────────────────────────────────────────────────

VALID_TRANSITIONS: dict[str, set[str]] = {
    "sent":              {"awaiting_response", "followup_due", "closed_won", "closed_lost"},
    "awaiting_response": {"followup_due", "closed_won", "closed_lost"},
    "followup_due":      {"followup_sent", "closed_won", "closed_lost"},
    "followup_sent":     {"awaiting_response", "closed_won", "closed_lost"},
    "closed_won":        set(),   # terminal
    "closed_lost":       set(),   # terminal
    # Legacy states (batch 7 records created with status='ready')
    "ready":             {"sent", "awaiting_response", "closed_lost"},
    "failed":            {"ready"},  # allow retry
}

ALL_STATES = set(VALID_TRANSITIONS.keys())


# ── FSM helpers ────────────────────────────────────────────────────────────────

def can_transition(from_state: str, to_state: str) -> bool:
    """Return True if the transition is permitted by the FSM."""
    return to_state in VALID_TRANSITIONS.get(from_state, set())


def validate_transition(from_state: str, to_state: str) -> tuple[bool, str]:
    """
    Validate a transition; return (ok, error_message).
    error_message is empty string on success.
    """
    if to_state not in ALL_STATES and to_state not in {"sent"}:
        return False, f"unknown target state '{to_state}'"
    if from_state in TERMINAL_STATES:
        return False, f"state '{from_state}' is terminal — no further transitions"
    if not can_transition(from_state, to_state):
        allowed = sorted(VALID_TRANSITIONS.get(from_state, set()))
        return False, (
            f"transition '{from_state}' → '{to_state}' is not allowed. "
            f"Allowed: {allowed}"
        )
    return True, ""


# ── Timing helpers ─────────────────────────────────────────────────────────────

def compute_next_action_at(channel: str, reference_iso: Optional[str] = None) -> str:
    """
    Compute the ISO-8601 datetime (Asia/Jerusalem) at which a follow-up
    should be triggered for the given channel.

    Args:
        channel:        outreach channel key
        reference_iso:  ISO start time; defaults to now (Asia/Jerusalem)

    Returns:
        ISO-8601 string in Asia/Jerusalem timezone
    """
    delay_h = FOLLOWUP_DELAY_HOURS.get(channel, DEFAULT_FOLLOWUP_HOURS)
    if reference_iso:
        try:
            # Parse regardless of offset info
            base = datetime.datetime.fromisoformat(reference_iso)
            if base.tzinfo is None:
                base = _IL_TZ.localize(base)
        except Exception:
            base = datetime.datetime.now(_IL_TZ)
    else:
        base = datetime.datetime.now(_IL_TZ)

    return (base + datetime.timedelta(hours=delay_h)).isoformat()


def is_followup_overdue(next_action_at_iso: Optional[str]) -> bool:
    """
    Return True if next_action_at has passed (i.e. follow-up is overdue).
    Returns False if next_action_at is None or cannot be parsed.
    """
    if not next_action_at_iso:
        return False
    try:
        dt = datetime.datetime.fromisoformat(next_action_at_iso)
        if dt.tzinfo is None:
            dt = _IL_TZ.localize(dt)
        return datetime.datetime.now(_IL_TZ) >= dt
    except Exception:
        log.warning(f"[Policy] could not parse next_action_at='{next_action_at_iso}'")
        return False
