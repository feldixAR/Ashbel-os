"""
services/growth/pipeline.py — E2E Strategic Growth Pipeline.

Flow:
    raw_goal (str)
        │
        ├─ [Goal Engine]      detect_domain / detect_metric / decompose_goal
        ├─ [Goal Engine]      identify_opportunities → raw opportunity dicts
        ├─ [Research Engine]  build_client_profile + build_market_map
        ├─ [Scoring]          score_all → List[ScoredOpportunity]   (numeric, 1–100)
        ├─ [Committee]        run_committee → CommitteeDecision       (Borda winner)
        ├─ [Goal Engine]      build_asset_draft + build_outreach_plan
        └─ [DB]               persist GoalModel + OpportunityModels
                │
                ▼
            PipelineResult
                ├── goal            {id, domain, metric, tracks}
                ├── research        {client_profile, market_map}
                ├── scored_opportunities  [ScoredOpportunity × N]
                ├── committee_decision    {winner, votes, reasoning, prioritized_actions}
                ├── asset_draft     {message, portfolio}
                └── outreach_plan   {sequence}

Trigger via Orchestrator:
    POST /api/command  {"command": "הגדל מכירות אלומיניום ב-30%"}
    → intent: SET_GOAL  → executor._handle_set_goal() → pipeline.run()
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from typing import List, Optional

log = logging.getLogger(__name__)


# ── Output contract ────────────────────────────────────────────────────────────

@dataclass
class PipelineResult:
    goal_id:    str
    raw_goal:   str
    domain:     str
    metric:     str
    tracks:     list
    research:   dict
    scored_opportunities: list       # List[ScoredOpportunity.to_dict()]
    committee_decision:   dict       # CommitteeDecision.to_dict()
    asset_draft:    dict
    outreach_plan:  dict
    success:    bool = True
    error:      Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "goal_id":               self.goal_id,
            "raw_goal":              self.raw_goal,
            "domain":                self.domain,
            "metric":                self.metric,
            "tracks":                self.tracks,
            "research":              self.research,
            "scored_opportunities":  self.scored_opportunities,
            "committee_decision":    self.committee_decision,
            "asset_draft":           self.asset_draft,
            "outreach_plan":         self.outreach_plan,
            "success":               self.success,
            "error":                 self.error,
        }


# ── Pipeline ───────────────────────────────────────────────────────────────────

def run(raw_goal: str) -> PipelineResult:
    """
    Execute the full E2E strategic growth pipeline.
    All errors are caught; returns PipelineResult(success=False) on failure.
    """
    goal_id = str(uuid.uuid4())
    log.info(f"[Pipeline] start goal_id={goal_id} goal='{raw_goal}'")

    try:
        # ── Step 1: Goal decomposition ────────────────────────────────────────
        from engines.goal_engine import (
            detect_domain, detect_metric,
            decompose_goal, identify_opportunities,
            build_asset_draft, build_outreach_plan,
        )
        domain  = detect_domain(raw_goal)
        metric  = detect_metric(raw_goal)
        decomp  = decompose_goal(raw_goal)
        tracks  = decomp["tracks"]
        log.info(f"[Pipeline] decomposed: domain={domain} metric={metric} tracks={len(tracks)}")

        # ── Step 2: Raw opportunities ─────────────────────────────────────────
        raw_opps = identify_opportunities(goal_id, tracks)
        log.info(f"[Pipeline] identified {len(raw_opps)} raw opportunities")

        # ── Step 3: Research (client profile + market map) ────────────────────
        from engines.research_engine import build_client_profile, build_market_map
        top_audience = tracks[0].get("audience", "general") if tracks else "general"
        top_channel  = tracks[0].get("channel",  "whatsapp") if tracks else "whatsapp"

        client_profile = build_client_profile(top_audience, domain)
        market_map     = build_market_map(domain)
        research = {
            "client_profile": (
                client_profile.__dict__
                if hasattr(client_profile, "__dict__") else str(client_profile)
            ),
            "market_map": (
                market_map.__dict__
                if hasattr(market_map, "__dict__") else str(market_map)
            ),
        }
        log.info(f"[Pipeline] research complete: audience={top_audience} domain={domain}")

        # ── Step 4: Numeric scoring ───────────────────────────────────────────
        from services.growth.scoring import score_all
        scored = score_all(raw_opps)
        log.info(
            f"[Pipeline] scored {len(scored)} opportunities — "
            f"top: '{scored[0].title}' score={scored[0].normalized_score}/100"
            if scored else "[Pipeline] no opportunities to score"
        )

        # ── Step 5: Growth Committee ──────────────────────────────────────────
        from services.growth.committee import run_committee
        decision = run_committee(scored)
        log.info(
            f"[Pipeline] committee winner='{decision.winner.title}' "
            f"borda={decision.winner_borda}"
        )

        # ── Step 6: Assets + outreach plan ────────────────────────────────────
        winner_opp = {
            "opp_id":      decision.winner.opp_id,
            "audience":    decision.winner.audience,
            "channel":     decision.winner.channel,
            "title":       decision.winner.title,
            "next_action": "",
        }
        asset_draft   = build_asset_draft(goal_id, decision.winner.audience, decision.winner.channel)
        outreach_plan = build_outreach_plan(goal_id, winner_opp)

        # ── Step 7: Persist to DB ─────────────────────────────────────────────
        _persist(goal_id, raw_goal, domain, metric, tracks, raw_opps)

        return PipelineResult(
            goal_id=goal_id,
            raw_goal=raw_goal,
            domain=domain,
            metric=metric,
            tracks=tracks,
            research=research,
            scored_opportunities=[o.to_dict() for o in scored[:6]],
            committee_decision=decision.to_dict(),
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
            research={},
            scored_opportunities=[],
            committee_decision={},
            asset_draft={},
            outreach_plan={},
            success=False,
            error=str(e),
        )


# ── DB persistence ─────────────────────────────────────────────────────────────

def _persist(
    goal_id: str,
    raw_goal: str,
    domain: str,
    metric: str,
    tracks: list,
    raw_opps: list,
) -> None:
    """Write GoalModel + OpportunityModels. Errors logged, not raised."""
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
                    id=opp.get("opp_id", str(uuid.uuid4())),
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
        log.info(f"[Pipeline] persisted goal_id={goal_id} opportunities={len(raw_opps)}")
    except Exception as e:
        log.error(f"[Pipeline] DB persist failed goal_id={goal_id}: {e}", exc_info=True)
