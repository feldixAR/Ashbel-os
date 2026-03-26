"""
growth_pipeline.py — End-to-end Goal → Prioritized Actions pipeline.

Flow:
    raw_goal (str)
        ↓ detect_domain / detect_metric
        ↓ decompose_goal          → tracks (list of audience segments)
        ↓ identify_opportunities  → raw opportunity dicts
        ↓ rank_opportunities      → List[OpportunityScore]  (numeric scores)
        ↓ committee_brainstorm    → CommitteeResult (winner persona + top path)
        ↓ build_research_summary  → audience insight
        ↓ build_asset_draft       → first message + portfolio template
        ↓ build_outreach_plan     → follow-up sequence
        ↓ PipelineResult          → persisted to DB, returned to caller

All DB writes happen here so executor._handle_set_goal stays thin.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from typing import List, Optional

log = logging.getLogger(__name__)


@dataclass
class PipelineResult:
    goal_id:          str
    raw_goal:         str
    domain:           str
    metric:           str
    tracks:           list
    top_opportunities: list           # List[OpportunityScore.to_dict()]
    committee:        dict            # CommitteeResult.to_dict()
    research:         dict
    asset_draft:      dict
    outreach_plan:    dict
    success:          bool = True
    error:            Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "goal_id":           self.goal_id,
            "raw_goal":          self.raw_goal,
            "domain":            self.domain,
            "metric":            self.metric,
            "tracks":            self.tracks,
            "top_opportunities": self.top_opportunities,
            "committee":         self.committee,
            "research":          self.research,
            "asset_draft":       self.asset_draft,
            "outreach_plan":     self.outreach_plan,
            "success":           self.success,
            "error":             self.error,
        }


def run_pipeline(raw_goal: str) -> PipelineResult:
    """
    Execute the full growth pipeline for a business objective.
    Persists GoalModel + OpportunityModels to DB.
    Returns PipelineResult with scored opportunities and winning committee proposal.
    """
    goal_id = str(uuid.uuid4())

    try:
        # ── 1. Classify ──────────────────────────────────────────────────────
        from engines.goal_engine import detect_domain, detect_metric, decompose_goal
        domain = detect_domain(raw_goal)
        metric = detect_metric(raw_goal)
        tracks = decompose_goal(raw_goal)
        log.info(f"[Pipeline] goal_id={goal_id} domain={domain} metric={metric} tracks={len(tracks)}")

        # ── 2. Identify raw opportunities ─────────────────────────────────────
        from engines.goal_engine import identify_opportunities
        raw_opps = identify_opportunities(goal_id, tracks)
        log.info(f"[Pipeline] identified {len(raw_opps)} raw opportunities")

        # ── 3. Score + rank ───────────────────────────────────────────────────
        from services.growth.opportunity_engine import rank_opportunities, committee_brainstorm
        scored = rank_opportunities(raw_opps)
        log.info(
            f"[Pipeline] top opportunity: '{scored[0].title}' score={scored[0].score:.1f}"
            if scored else "[Pipeline] no opportunities scored"
        )

        # ── 4. Growth Committee brainstorm ─────────────────────────────────────
        committee_result = committee_brainstorm(scored)

        # ── 5. Research + assets ──────────────────────────────────────────────
        top_audience = scored[0].audience if scored else "general"
        top_channel  = scored[0].channel  if scored else "whatsapp"
        from engines.goal_engine import build_research_summary, build_asset_draft, build_outreach_plan
        research     = build_research_summary(goal_id, domain, top_audience)
        asset_draft  = build_asset_draft(goal_id, top_audience, top_channel)
        top_opp_dict = scored[0].to_dict() if scored else {}
        outreach_plan = build_outreach_plan(goal_id, top_opp_dict)

        # ── 6. Persist to DB ──────────────────────────────────────────────────
        _persist(goal_id, raw_goal, domain, metric, tracks, raw_opps)

        return PipelineResult(
            goal_id=goal_id,
            raw_goal=raw_goal,
            domain=domain,
            metric=metric,
            tracks=tracks,
            top_opportunities=[o.to_dict() for o in scored[:5]],
            committee=committee_result.to_dict(),
            research=research,
            asset_draft=asset_draft,
            outreach_plan=outreach_plan,
        )

    except Exception as e:
        log.error(f"[Pipeline] failed goal_id={goal_id}: {e}", exc_info=True)
        return PipelineResult(
            goal_id=goal_id,
            raw_goal=raw_goal,
            domain="unknown",
            metric="unknown",
            tracks=[],
            top_opportunities=[],
            committee={},
            research={},
            asset_draft={},
            outreach_plan={},
            success=False,
            error=str(e),
        )


def _persist(
    goal_id: str,
    raw_goal: str,
    domain: str,
    metric: str,
    tracks: list,
    raw_opps: list,
) -> None:
    """Write GoalModel + OpportunityModels to DB. Errors are logged, not raised."""
    try:
        from services.storage.db import get_session
        from services.storage.models.goal import GoalModel
        from services.storage.models.opportunity import OpportunityModel

        with get_session() as session:
            session.add(GoalModel(
                id=goal_id,
                raw_goal=raw_goal,
                domain=domain,
                primary_metric=metric,
                status="active",
                tracks=tracks,
            ))
            for opp in raw_opps:
                session.add(OpportunityModel(
                    id=str(uuid.uuid4()),
                    goal_id=goal_id,
                    track_id=opp.get("track_id", ""),
                    title=opp.get("title", ""),
                    audience=opp.get("audience", ""),
                    channel=opp.get("channel", "whatsapp"),
                    potential=opp.get("potential", "medium"),
                    effort=opp.get("effort", "medium"),
                    next_action=opp.get("next_action", ""),
                    status="open",
                ))
        log.info(f"[Pipeline] persisted goal_id={goal_id} opps={len(raw_opps)}")
    except Exception as e:
        log.error(f"[Pipeline] DB persist failed goal_id={goal_id}: {e}", exc_info=True)
