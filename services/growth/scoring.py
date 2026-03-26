"""
services/growth/scoring.py — Numeric opportunity scoring.

Formula (base):
    raw_score  = (revenue_potential * success_probability) / effort
    normalized = clamp(round((raw_score / MAX_RAW) * 100), 1, 100)

Learning Multiplier (Batch 10):
    Fetches PerformanceMetric for the opportunity's audience and channel.
    multiplier = clamp(1.0 + (conversion_rate - BASE_RATE) * WEIGHT, MIN_M, MAX_M)
    final_score = clamp(round(normalized * multiplier), 1, 100)

    BASE_RATE = 0.20  (20% baseline before any learning data)
    WEIGHT    = 2.0   (each +10pp conversion → +20% score boost)
    MIN_M     = 0.5   (floor: heavily underperforming segments)
    MAX_M     = 2.0   (ceiling: top-converting segments double score)

Calibration (Ashbal Aluminum, AVG_DEAL = ₪15,000):
    revenue_potential  high=25000  medium=15000  low=8000   (ILS)
    success_probability high=0.70  medium=0.40   low=0.20
    effort              low=10     medium=30      high=80    (hours to close)
    MAX_RAW = (25000 * 0.70) / 10 = 1750
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import List, Optional

log = logging.getLogger(__name__)

# ── Lookup tables ─────────────────────────────────────────────────────────────

_REVENUE: dict[str, int]  = {"high": 25_000, "medium": 15_000, "low": 8_000}
_PROB:    dict[str, float] = {"high": 0.70,   "medium": 0.40,   "low": 0.20}
_EFFORT:  dict[str, int]   = {"low":  10,      "medium": 30,     "high": 80}
_MAX_RAW: float            = (_REVENUE["high"] * _PROB["high"]) / _EFFORT["low"]   # 1750.0

# Learning multiplier config
_BASE_RATE = 0.20
_WEIGHT    = 2.0
_MIN_M     = 0.5
_MAX_M     = 2.0


# ── Output contract ────────────────────────────────────────────────────────────

@dataclass
class ScoredOpportunity:
    # identity
    opp_id:   str
    title:    str
    audience: str
    channel:  str
    # numeric inputs
    revenue_potential:    int    # ILS
    success_probability:  float  # 0–1
    effort:               int    # hours
    # scores
    raw_score:          float   # (revenue * probability) / effort
    normalized_score:   int     # 1–100 (base formula)
    learning_multiplier: float  = 1.0   # applied from PerformanceMetric
    final_score:        int     = 0     # normalized_score * learning_multiplier, clamped

    def __post_init__(self):
        if self.final_score == 0:
            self.final_score = self.normalized_score

    def to_dict(self) -> dict:
        return {
            "opp_id":               self.opp_id,
            "title":                self.title,
            "audience":             self.audience,
            "channel":              self.channel,
            "revenue_potential":    self.revenue_potential,
            "success_probability":  self.success_probability,
            "effort_hours":         self.effort,
            "raw_score":            round(self.raw_score, 2),
            "normalized_score":     self.normalized_score,
            "learning_multiplier":  round(self.learning_multiplier, 3),
            "final_score":          self.final_score,
        }


# ── Learning multiplier cache ──────────────────────────────────────────────────

# Module-level cache: (dim_type, dim_value) → conversion_rate
# Populated once per score_all() call; stale after process restart (acceptable).
_metric_cache: dict[tuple, float] = {}


def _load_metrics() -> None:
    """Populate _metric_cache from PerformanceMetric table. Fails silently."""
    global _metric_cache
    try:
        from services.storage.db import get_session
        from services.storage.models.analytics import PerformanceMetric

        with get_session() as session:
            rows = session.query(
                PerformanceMetric.dim_type,
                PerformanceMetric.dim_value,
                PerformanceMetric.conversion_rate,
            ).filter(PerformanceMetric.sample_size >= 3).all()

        _metric_cache = {(r.dim_type, r.dim_value): r.conversion_rate for r in rows}
        log.debug(f"[Scoring] Loaded {len(_metric_cache)} metric entries")
    except Exception as e:
        log.warning(f"[Scoring] Could not load PerformanceMetrics: {e}")
        _metric_cache = {}


def _multiplier(audience: str, channel: str) -> float:
    """
    Return the learning multiplier for a given audience + channel combination.
    Uses the higher of the two individual rates (audience takes priority if both exist).
    Returns 1.0 (neutral) if no data or below minimum sample threshold.
    """
    aud_rate = _metric_cache.get(("audience", audience))
    ch_rate  = _metric_cache.get(("channel",  channel))

    # Prefer audience signal; fall back to channel; fall back to baseline
    rate = aud_rate if aud_rate is not None else ch_rate
    if rate is None:
        return 1.0

    m = 1.0 + (rate - _BASE_RATE) * _WEIGHT
    return round(max(_MIN_M, min(_MAX_M, m)), 4)


# ── Core functions ─────────────────────────────────────────────────────────────

def score_one(opp: dict, apply_learning: bool = True) -> ScoredOpportunity:
    """Score a single raw opportunity dict. All string fields converted to numeric."""
    potential = (opp.get("potential") or "medium").lower()
    effort_s  = (opp.get("effort")    or "medium").lower()

    revenue = _REVENUE.get(potential, _REVENUE["medium"])
    prob    = _PROB.get(potential,    _PROB["medium"])
    effort  = _EFFORT.get(effort_s,   _EFFORT["medium"])

    raw        = (revenue * prob) / effort
    normalized = int(min(100, max(1, round((raw / _MAX_RAW) * 100))))

    audience = opp.get("audience", "general")
    channel  = opp.get("channel",  "whatsapp")

    mult        = _multiplier(audience, channel) if apply_learning else 1.0
    final_score = int(min(100, max(1, round(normalized * mult))))

    return ScoredOpportunity(
        opp_id=opp.get("opp_id", ""),
        title=opp.get("title", ""),
        audience=audience,
        channel=channel,
        revenue_potential=revenue,
        success_probability=prob,
        effort=effort,
        raw_score=raw,
        normalized_score=normalized,
        learning_multiplier=mult,
        final_score=final_score,
    )


def score_all(opportunities: list) -> List[ScoredOpportunity]:
    """
    Score and rank a list of raw opportunity dicts.
    Loads PerformanceMetrics once, applies learning multiplier per opp.
    Returns sorted by final_score descending.
    """
    _load_metrics()
    scored = [score_one(o, apply_learning=True) for o in opportunities]
    scored.sort(key=lambda x: x.final_score, reverse=True)
    return scored
