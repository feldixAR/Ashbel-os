"""
opportunity_engine.py — Numeric scoring + Growth Committee brainstorm.

Scoring formula:  score = (expected_revenue_ils * probability) / effort_hours

Revenue mapping (Ashbal Aluminum, AVG_DEAL = ₪15,000):
    high   → ₪25,000   (premium projects: architects, multi-unit contractors)
    medium → ₪15,000   (standard deal)
    low    → ₪8,000    (small jobs, first contacts)

Probability mapping:
    high   → 0.70
    medium → 0.40
    low    → 0.20

Effort mapping (hours to close):
    low    → 10h
    medium → 30h
    high   → 80h

Growth Committee:
    Three internal personas each rank the opportunity set from their perspective,
    proposing a "top path". The Orchestrator selects the highest-scored winner.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import List, Optional

log = logging.getLogger(__name__)

# ── Ashbal-specific calibration ───────────────────────────────────────────────

_REVENUE_ILS = {"high": 25_000, "medium": 15_000, "low": 8_000}
_PROBABILITY  = {"high": 0.70,  "medium": 0.40,   "low": 0.20}
_EFFORT_HOURS = {"low":  10,    "medium": 30,      "high": 80}


# ── Data contracts ─────────────────────────────────────────────────────────────

@dataclass
class OpportunityScore:
    title:               str
    audience:            str
    channel:             str
    expected_revenue_ils: int
    probability:         float
    effort_hours:        int
    score:               float          # (revenue * probability) / effort
    rationale:           str
    next_action:         str = ""

    def to_dict(self) -> dict:
        return {
            "title":               self.title,
            "audience":            self.audience,
            "channel":             self.channel,
            "expected_revenue_ils": self.expected_revenue_ils,
            "probability":         self.probability,
            "effort_hours":        self.effort_hours,
            "score":               round(self.score, 2),
            "rationale":           self.rationale,
            "next_action":         self.next_action,
        }


@dataclass
class CommitteeProposal:
    persona:      str          # "sales" | "operations" | "strategy"
    top_path:     str          # one-line description of recommended approach
    opportunities: List[OpportunityScore] = field(default_factory=list)
    total_score:  float = 0.0

    def to_dict(self) -> dict:
        return {
            "persona":      self.persona,
            "top_path":     self.top_path,
            "total_score":  round(self.total_score, 2),
            "opportunities": [o.to_dict() for o in self.opportunities[:3]],
        }


@dataclass
class CommitteeResult:
    winner:    CommitteeProposal
    all_proposals: List[CommitteeProposal]
    rationale: str

    def to_dict(self) -> dict:
        return {
            "winner":        self.winner.to_dict(),
            "all_proposals": [p.to_dict() for p in self.all_proposals],
            "rationale":     self.rationale,
        }


# ── Scoring ────────────────────────────────────────────────────────────────────

def score_opportunity(opp: dict) -> OpportunityScore:
    """
    Convert a raw opportunity dict (from goal_engine.identify_opportunities)
    into a scored OpportunityScore using the formula:
        score = (expected_revenue_ils * probability) / effort_hours
    """
    potential = (opp.get("potential") or "medium").lower()
    effort    = (opp.get("effort")    or "medium").lower()
    audience  = opp.get("audience", "general")
    channel   = opp.get("channel", "whatsapp")

    revenue      = _REVENUE_ILS.get(potential,  _REVENUE_ILS["medium"])
    probability  = _PROBABILITY.get(potential,  _PROBABILITY["medium"])
    effort_hours = _EFFORT_HOURS.get(effort,    _EFFORT_HOURS["medium"])

    score = (revenue * probability) / effort_hours

    rationale = (
        f"הכנסה צפויה ₪{revenue:,} × הסתברות {int(probability*100)}% "
        f"÷ {effort_hours}ש עבודה = {score:.1f} ₪/ש"
    )

    return OpportunityScore(
        title=opp.get("title", ""),
        audience=audience,
        channel=channel,
        expected_revenue_ils=revenue,
        probability=probability,
        effort_hours=effort_hours,
        score=score,
        rationale=rationale,
        next_action=opp.get("next_action", ""),
    )


def rank_opportunities(opps: list) -> List[OpportunityScore]:
    """Score and sort a list of raw opportunity dicts, highest score first."""
    scored = [score_opportunity(o) for o in opps]
    scored.sort(key=lambda x: x.score, reverse=True)
    return scored


# ── Growth Committee ───────────────────────────────────────────────────────────

class _SalesPersona:
    """
    Focuses on: quick wins, warm contacts, WhatsApp outreach, low effort.
    Bias: prefer low-effort + medium/high potential.
    """
    name = "sales"

    def propose(self, scored: List[OpportunityScore]) -> CommitteeProposal:
        # Prefer low-effort opportunities — quick revenue
        preferred = [o for o in scored if o.effort_hours <= 15]
        if not preferred:
            preferred = scored[:3]
        preferred = sorted(preferred, key=lambda x: x.score, reverse=True)[:3]
        total     = sum(o.score for o in preferred)

        return CommitteeProposal(
            persona="sales",
            top_path=(
                "מיקוד בלידים חמים ויצירת קשר מהיר דרך וואטסאפ. "
                "מטרה: 3 פגישות תוך שבוע."
            ),
            opportunities=preferred,
            total_score=total,
        )


class _OperationsPersona:
    """
    Focuses on: scalable processes, contractor partnerships, repeat business.
    Bias: prefer medium/high-effort opportunities with high potential.
    """
    name = "operations"

    def propose(self, scored: List[OpportunityScore]) -> CommitteeProposal:
        # Prefer high-potential → sustainable pipeline
        preferred = [o for o in scored if o.expected_revenue_ils >= 15_000]
        if not preferred:
            preferred = scored[:3]
        preferred = sorted(preferred, key=lambda x: x.expected_revenue_ils, reverse=True)[:3]
        total     = sum(o.score for o in preferred)

        return CommitteeProposal(
            persona="operations",
            top_path=(
                "בניית שותפויות חוזרות עם קבלנים פעילים. "
                "מטרה: 2 הסכמי ספק קבוע תוך חודש."
            ),
            opportunities=preferred,
            total_score=total,
        )


class _StrategyPersona:
    """
    Focuses on: architect relationships, long-term positioning, brand.
    Bias: prefer highest-score opportunities regardless of effort.
    """
    name = "strategy"

    def propose(self, scored: List[OpportunityScore]) -> CommitteeProposal:
        preferred = scored[:3]   # top-scored overall
        total     = sum(o.score for o in preferred)

        return CommitteeProposal(
            persona="strategy",
            top_path=(
                "מיצוב אשבל כספק מועדף של אדריכלים ומעצבים. "
                "מטרה: 5 קשרי אדריכלים חדשים תוך רבעון."
            ),
            opportunities=preferred,
            total_score=total,
        )


_COMMITTEE = [_SalesPersona(), _OperationsPersona(), _StrategyPersona()]


def committee_brainstorm(scored_opportunities: List[OpportunityScore]) -> CommitteeResult:
    """
    Run all 3 personas against the scored opportunity list.
    Select the proposal with the highest total_score as the winner.
    """
    proposals = [persona.propose(scored_opportunities) for persona in _COMMITTEE]
    proposals.sort(key=lambda p: p.total_score, reverse=True)
    winner = proposals[0]

    rationale = (
        f"ועדת הצמיחה בחרה במסלול '{winner.persona}' "
        f"עם ניקוד כולל {winner.total_score:.1f}. "
        f"{winner.top_path}"
    )

    log.info(
        f"[GrowthCommittee] winner={winner.persona} score={winner.total_score:.1f} "
        f"| proposals={[f'{p.persona}:{p.total_score:.1f}' for p in proposals]}"
    )

    return CommitteeResult(
        winner=winner,
        all_proposals=proposals,
        rationale=rationale,
    )
