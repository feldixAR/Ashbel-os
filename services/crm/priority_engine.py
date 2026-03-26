"""
services/crm/priority_engine.py — Priority & Time Allocation Engine.

score_deal(deal)   → float 0-100  (value × probability / days_to_close)
score_lead(lead)   → float 0-100  (recency + score + status weight)
allocate_time(items, budget_minutes) → List[TimeBlock]

Priority formula:
    deal_score = (value_ils × probability) / max(days_to_close, 1)
    normalised to 0-100 against the current portfolio ceiling.

Time allocation:
    Each item gets a time block proportional to its priority score.
    Minimum block: 15 min. Maximum single block: 60 min.
"""

from __future__ import annotations

import datetime
import logging
from dataclasses import dataclass, field
from typing import List, Optional

import pytz

log = logging.getLogger(__name__)
_IL_TZ = pytz.timezone("Asia/Jerusalem")

_MIN_BLOCK   = 15    # minutes
_MAX_BLOCK   = 60    # minutes
_DEFAULT_DAY = 240   # minutes of selling time per day


@dataclass
class PriorityItem:
    item_id:    str
    item_type:  str   # deal | lead
    title:      str
    score:      float
    reason:     str
    metadata:   dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "item_id":   self.item_id,
            "item_type": self.item_type,
            "title":     self.title,
            "score":     round(self.score, 2),
            "reason":    self.reason,
            "metadata":  self.metadata,
        }


@dataclass
class TimeBlock:
    item_id:      str
    title:        str
    minutes:      int
    start_offset: int   # minutes from start of day slot
    action:       str

    def to_dict(self) -> dict:
        return {
            "item_id":      self.item_id,
            "title":        self.title,
            "minutes":      self.minutes,
            "start_offset": self.start_offset,
            "action":       self.action,
        }


# ── Scoring ────────────────────────────────────────────────────────────────────

def score_deal(deal) -> float:
    """Score a DealModel. Returns 0-100 raw (not yet normalised against portfolio)."""
    if deal.stage in ("won", "lost"):
        return 0.0
    prob     = float(deal.probability or 0.20)
    value    = int(deal.value_ils or 0)
    weighted = value * prob

    days = _days_to_close(deal.expected_close_date)
    return weighted / max(days, 1)


def score_lead(lead) -> float:
    """Score a LeadModel on urgency. Returns 0-100."""
    _STATUS_W = {
        "חם":        100,
        "בטיפול":    70,
        "חדש":       50,
        "קר":        20,
        "לא רלוונטי": 0,
    }
    base = _STATUS_W.get(lead.status or "חדש", 50)
    score_bonus = min(float(lead.score or 0), 40)   # lead engine score capped at 40
    return min(100.0, base + score_bonus * 0.5)


def build_priority_list(deals: list, leads: list) -> List[PriorityItem]:
    """
    Combine deals and leads into a single ranked priority list.
    Deals first (revenue-driving), then leads without a deal.
    """
    items: List[PriorityItem] = []

    # Score deals
    deal_scores = [(d, score_deal(d)) for d in deals if d.stage not in ("won", "lost")]
    max_deal    = max((s for _, s in deal_scores), default=1.0)

    for deal, raw in deal_scores:
        normalised = min(100.0, (raw / max_deal) * 100)
        items.append(PriorityItem(
            item_id=deal.id,
            item_type="deal",
            title=deal.title,
            score=normalised,
            reason=f"שלב: {deal.stage} | ₪{deal.value_ils:,} × {int(deal.probability*100)}%",
            metadata={"stage": deal.stage, "value": deal.value_ils,
                      "lead_id": deal.lead_id},
        ))

    # Score leads not already represented by an active deal
    deal_lead_ids = {d.lead_id for d, _ in deal_scores}
    for lead in leads:
        if lead.id in deal_lead_ids:
            continue
        s = score_lead(lead)
        if s < 10:
            continue
        items.append(PriorityItem(
            item_id=lead.id,
            item_type="lead",
            title=lead.name,
            score=s,
            reason=f"סטטוס: {lead.status} | ניקוד: {lead.score or 0}",
            metadata={"status": lead.status, "phone": lead.phone},
        ))

    items.sort(key=lambda x: x.score, reverse=True)
    return items


def allocate_time(
    items: List[PriorityItem],
    budget_minutes: int = _DEFAULT_DAY,
) -> List[TimeBlock]:
    """
    Allocate daily time budget across priority items proportionally.
    Top item gets the largest block; minimum 15min, maximum 60min.
    """
    if not items:
        return []

    total_score = sum(i.score for i in items) or 1.0
    blocks: List[TimeBlock] = []
    offset = 0

    for item in items:
        if offset >= budget_minutes:
            break
        fraction = item.score / total_score
        minutes  = int(fraction * budget_minutes)
        minutes  = max(_MIN_BLOCK, min(_MAX_BLOCK, minutes))
        minutes  = min(minutes, budget_minutes - offset)

        action = (
            f"טפל בעסקה: {item.title}" if item.item_type == "deal"
            else f"צור קשר עם: {item.title}"
        )
        blocks.append(TimeBlock(
            item_id=item.item_id,
            title=item.title,
            minutes=minutes,
            start_offset=offset,
            action=action,
        ))
        offset += minutes

    return blocks


# ── Helper ─────────────────────────────────────────────────────────────────────

def _days_to_close(expected_close_date: Optional[str]) -> float:
    if not expected_close_date:
        return 30.0
    try:
        target = datetime.date.fromisoformat(expected_close_date)
        today  = datetime.datetime.now(_IL_TZ).date()
        delta  = (target - today).days
        return max(float(delta), 1.0)
    except Exception:
        return 30.0
