"""
LeadEngine — pure lead scoring and filtering logic.

No side effects. No event emission. No DB writes.
Agents call these functions and own the side effects.

Functions:
    compute_score(lead)              -> int (0-100)
    filter_for_followup(leads)       -> List[LeadModel]
    filter_hot(leads, min_score)     -> List[LeadModel]
    rank(leads)                      -> List[LeadModel] sorted by score desc
"""

import logging
from typing import List, TYPE_CHECKING

from config.company_profile import LEAD_SCORE_WEIGHTS

if TYPE_CHECKING:
    from services.storage.models.lead import LeadModel

log = logging.getLogger(__name__)


def compute_score(lead) -> int:
    """
    Compute a lead score (0-100) using LEAD_SCORE_WEIGHTS from company_profile.
    Pure function — no I/O, no side effects.
    """
    score = 0
    w     = LEAD_SCORE_WEIGHTS

    # Source weight
    score += w.get("source", {}).get(lead.source or "manual", 0)

    # City tier
    city  = (lead.city or "").strip()
    tiers = w.get("city_tier", {})
    if city in tiers.get("tier_1", []):
        score += tiers.get("tier_1_score", 0)
    elif city in tiers.get("tier_2", []):
        score += tiers.get("tier_2_score", 0)
    else:
        score += tiers.get("other_score", 0)

    # Positive response
    response = (lead.response or "").strip()
    if response and response.lower() not in ("", "אין", "אין תגובה", "none"):
        score += w.get("response_positive", 0)

    # No-attempt bonus
    if (lead.attempts or 0) == 0:
        score += w.get("no_attempts_bonus", 0)

    # Repeated no-response penalty
    if (lead.attempts or 0) > 3 and not response:
        score += w.get("repeated_no_response_penalty", 0)

    return max(0, min(100, score))


def filter_for_followup(leads: list, max_attempts: int = 5) -> list:
    """
    Return leads that are eligible for follow-up:
        - status in (חדש, ניסיון קשר, מתעניין)
        - attempts < max_attempts
    Sorted by score descending.
    """
    eligible = [
        l for l in leads
        if (l.attempts or 0) < max_attempts
        and (l.status or "") in ("חדש", "ניסיון קשר", "מתעניין")
    ]
    return sorted(eligible, key=lambda l: l.score or 0, reverse=True)


def filter_hot(leads: list, min_score: int = 70) -> list:
    """
    Return leads with score >= min_score, excluding closed ones.
    Sorted by score descending.
    """
    closed = {"סגור_זכה", "סגור_הפסיד"}
    hot = [
        l for l in leads
        if (l.score or 0) >= min_score
        and (l.status or "") not in closed
    ]
    return sorted(hot, key=lambda l: l.score or 0, reverse=True)


def rank(leads: list) -> list:
    """Return leads sorted by score descending."""
    return sorted(leads, key=lambda l: l.score or 0, reverse=True)
