"""
services/growth/scoring.py — Numeric opportunity scoring.

Formula:
    raw_score  = (revenue_potential * success_probability) / effort
    normalized = clamp(round((raw_score / MAX_RAW) * 100), 1, 100)

Calibration (Ashbal Aluminum, AVG_DEAL = ₪15,000):
    revenue_potential  high=25000  medium=15000  low=8000   (ILS)
    success_probability high=0.70  medium=0.40   low=0.20
    effort              low=10     medium=30      high=80    (hours to close)

    MAX_RAW = (25000 * 0.70) / 10 = 1750  → normalized score ceiling
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List

# ── Lookup tables ─────────────────────────────────────────────────────────────

_REVENUE: dict[str, int]   = {"high": 25_000, "medium": 15_000, "low": 8_000}
_PROB:    dict[str, float]  = {"high": 0.70,   "medium": 0.40,   "low": 0.20}
_EFFORT:  dict[str, int]    = {"low":  10,      "medium": 30,     "high": 80}
_MAX_RAW: float             = (_REVENUE["high"] * _PROB["high"]) / _EFFORT["low"]   # 1750.0


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
    raw_score:        float   # (revenue * probability) / effort
    normalized_score: int     # 1–100

    def to_dict(self) -> dict:
        return {
            "opp_id":              self.opp_id,
            "title":               self.title,
            "audience":            self.audience,
            "channel":             self.channel,
            "revenue_potential":   self.revenue_potential,
            "success_probability": self.success_probability,
            "effort_hours":        self.effort,
            "raw_score":           round(self.raw_score, 2),
            "normalized_score":    self.normalized_score,
        }


# ── Core functions ─────────────────────────────────────────────────────────────

def score_one(opp: dict) -> ScoredOpportunity:
    """Score a single raw opportunity dict. All string fields converted to numeric."""
    potential = (opp.get("potential") or "medium").lower()
    effort_s  = (opp.get("effort")    or "medium").lower()

    revenue = _REVENUE.get(potential, _REVENUE["medium"])
    prob    = _PROB.get(potential,    _PROB["medium"])
    effort  = _EFFORT.get(effort_s,   _EFFORT["medium"])

    raw        = (revenue * prob) / effort
    normalized = int(min(100, max(1, round((raw / _MAX_RAW) * 100))))

    return ScoredOpportunity(
        opp_id=opp.get("opp_id", ""),
        title=opp.get("title", ""),
        audience=opp.get("audience", "general"),
        channel=opp.get("channel", "whatsapp"),
        revenue_potential=revenue,
        success_probability=prob,
        effort=effort,
        raw_score=raw,
        normalized_score=normalized,
    )


def score_all(opportunities: list) -> List[ScoredOpportunity]:
    """Score and rank a list of raw opportunity dicts. Highest normalized_score first."""
    scored = [score_one(o) for o in opportunities]
    scored.sort(key=lambda x: x.normalized_score, reverse=True)
    return scored
