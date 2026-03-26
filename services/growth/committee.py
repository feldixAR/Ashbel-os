"""
services/growth/committee.py — Multi-Persona Growth Committee.

Three personas evaluate the scored opportunity list from distinct angles:

    Revenue_Maximizer — Which opportunities yield the most revenue per hour?
                        Ranks by (revenue_potential * success_probability) descending.

    Speed_Runner      — Which can we close fastest?
                        Ranks by effort ascending (fewest hours to close).

    Strategic_Fit     — Which best fits long-term domain positioning?
                        Ranks by normalized_score descending (balanced formula).

Each persona produces a PersonaVote (top 3 picks + rationale).
The committee aggregates votes via a Borda-count style rank sum:
    - A pick ranked 1st by any persona earns 3 pts
    - 2nd → 2 pts, 3rd → 1 pt
The opportunity with the highest aggregate Borda score becomes the
committee_decision.winner.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import List, Optional

from services.growth.scoring import ScoredOpportunity

log = logging.getLogger(__name__)


# ── Data contracts ─────────────────────────────────────────────────────────────

@dataclass
class PersonaVote:
    persona:   str                          # "Revenue_Maximizer" | "Speed_Runner" | "Strategic_Fit"
    top_picks: List[ScoredOpportunity]      # ordered list, max 3
    rationale: str
    recommended_action: str

    def to_dict(self) -> dict:
        return {
            "persona":            self.persona,
            "top_picks":          [o.to_dict() for o in self.top_picks],
            "rationale":          self.rationale,
            "recommended_action": self.recommended_action,
        }


@dataclass
class CommitteeDecision:
    winner:           ScoredOpportunity
    winner_borda:     int
    votes:            List[PersonaVote]
    reasoning:        str
    prioritized_actions: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "winner":             self.winner.to_dict(),
            "winner_borda_score": self.winner_borda,
            "votes":              [v.to_dict() for v in self.votes],
            "reasoning":          self.reasoning,
            "prioritized_actions": self.prioritized_actions,
        }


# ── Personas ───────────────────────────────────────────────────────────────────

class _RevenueMaximizer:
    name = "Revenue_Maximizer"

    def vote(self, scored: List[ScoredOpportunity]) -> PersonaVote:
        picks = sorted(
            scored,
            key=lambda o: o.revenue_potential * o.success_probability,
            reverse=True,
        )[:3]
        top = picks[0] if picks else None
        return PersonaVote(
            persona=self.name,
            top_picks=picks,
            rationale=(
                f"מיקוד בהכנסה מרבית: {top.title} — "
                f"₪{top.revenue_potential:,} × {int(top.success_probability*100)}% = "
                f"₪{int(top.revenue_potential * top.success_probability):,} ערך צפוי"
                if top else "אין הזדמנויות"
            ),
            recommended_action=(
                f"פנה ל-{top.audience} דרך {top.channel} — "
                f"ערך עסקה גבוה ביותר"
                if top else ""
            ),
        )


class _SpeedRunner:
    name = "Speed_Runner"

    def vote(self, scored: List[ScoredOpportunity]) -> PersonaVote:
        picks = sorted(scored, key=lambda o: o.effort)[:3]
        top = picks[0] if picks else None
        return PersonaVote(
            persona=self.name,
            top_picks=picks,
            rationale=(
                f"ניצחון מהיר: {top.title} — "
                f"דורש {top.effort} שעות בלבד לסגירה"
                if top else "אין הזדמנויות"
            ),
            recommended_action=(
                f"שלח הודעה ראשונה ל-{top.audience} תוך 24 שעות"
                if top else ""
            ),
        )


class _StrategicFit:
    name = "Strategic_Fit"

    def vote(self, scored: List[ScoredOpportunity]) -> PersonaVote:
        picks = sorted(scored, key=lambda o: o.normalized_score, reverse=True)[:3]
        top = picks[0] if picks else None
        return PersonaVote(
            persona=self.name,
            top_picks=picks,
            rationale=(
                f"התאמה אסטרטגית: {top.title} — "
                f"ניקוד מאוזן {top.normalized_score}/100 "
                f"(הכנסה + הסתברות + מאמץ)"
                if top else "אין הזדמנויות"
            ),
            recommended_action=(
                f"בנה נכס שיווקי מותאם ל-{top.audience} ו-{top.channel}"
                if top else ""
            ),
        )


_PERSONAS = [_RevenueMaximizer(), _SpeedRunner(), _StrategicFit()]
_BORDA_POINTS = {0: 3, 1: 2, 2: 1}   # rank → points


# ── Committee aggregation ──────────────────────────────────────────────────────

def run_committee(scored: List[ScoredOpportunity]) -> CommitteeDecision:
    """
    Run all 3 personas, aggregate via Borda count, return CommitteeDecision.
    """
    if not scored:
        raise ValueError("committee requires at least one scored opportunity")

    votes: List[PersonaVote] = [p.vote(scored) for p in _PERSONAS]

    # Borda count: tally points per opp_id
    borda: dict[str, int] = {}
    for vote in votes:
        for rank, opp in enumerate(vote.top_picks):
            pts = _BORDA_POINTS.get(rank, 0)
            borda[opp.opp_id] = borda.get(opp.opp_id, 0) + pts

    # Map opp_id → ScoredOpportunity for lookup
    opp_map = {o.opp_id: o for o in scored}

    # Winner = highest Borda score; tie → highest normalized_score
    winner_id = max(
        borda,
        key=lambda oid: (borda[oid], opp_map.get(oid, scored[0]).normalized_score),
    )
    winner      = opp_map.get(winner_id, scored[0])
    winner_pts  = borda[winner_id]

    persona_names = [v.persona for v in votes if any(p.opp_id == winner_id for p in v.top_picks)]
    reasoning = (
        f"ועדת הצמיחה בחרה: '{winner.title}' "
        f"(ניקוד בורדה {winner_pts}, ניקוד מנורמל {winner.normalized_score}/100). "
        f"נתמך על ידי: {', '.join(persona_names)}."
    )

    prioritized_actions = _build_actions(winner, votes)

    log.info(
        f"[Committee] winner='{winner.title}' borda={winner_pts} "
        f"normalized={winner.normalized_score} supporters={persona_names}"
    )

    return CommitteeDecision(
        winner=winner,
        winner_borda=winner_pts,
        votes=votes,
        reasoning=reasoning,
        prioritized_actions=prioritized_actions,
    )


def _build_actions(winner: ScoredOpportunity, votes: List[PersonaVote]) -> List[str]:
    """Build a deduplicated list of prioritized actions from all persona recommendations."""
    actions = []
    # Winner's own action first
    actions.append(f"[מנצח] {winner.title}: פנייה ל-{winner.audience} דרך {winner.channel}")
    # Then each persona's recommended_action
    for vote in votes:
        if vote.recommended_action and vote.recommended_action not in actions:
            actions.append(f"[{vote.persona}] {vote.recommended_action}")
    return actions
