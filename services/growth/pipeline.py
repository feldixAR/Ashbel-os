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
        ├─ [AssetFactory]     generate_assets → AssetBundle           (whatsapp/email/brief)
        ├─ [ExecutionRecord]  persist → List[ExecutionRecord]         (status=ready)
        └─ [DB]               persist GoalModel + OpportunityModels
                │
                ▼
            PipelineResult
                ├── goal_id, domain, metric, tracks
                ├── research               {client_profile, market_map}
                ├── scored_opportunities   [ScoredOpportunity × N]
                ├── committee_decision     {winner, votes, reasoning, prioritized_actions}
                ├── asset_draft            {message, portfolio}
                ├── outreach_plan          {sequence}
                ├── generated_assets       {assets: [whatsapp, email, brief], primary_asset}
                ├── execution_record_id    str   (primary OutreachModel.id)
                └── execution_records      [ExecutionRecord × 3]

Trigger via Orchestrator:
    POST /api/command  {"command": "הגדל מכירות אלומיניום ב-30%"}
    → intent: SET_GOAL  → executor._handle_set_goal() → pipeline.run()
"""

from __future__ import annotations

import json as _json
import logging
import uuid
from dataclasses import dataclass, field
from typing import List, Optional

import pytz as _pytz
import datetime as _dt

log = logging.getLogger(__name__)
_IL_TZ = _pytz.timezone("Asia/Jerusalem")


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
    # Batch 7 — generated assets + execution record
    generated_assets:      dict = field(default_factory=dict)  # AssetBundle.to_dict()
    execution_record_id:   str  = ""    # primary OutreachModel.id for the winner's channel
    execution_records:     list = field(default_factory=list)  # all ExecutionRecord.to_dict()
    # Batch 8 — dispatch result
    delivery_status:       str  = ""   # delivered | failed | skipped
    provider_message_id:   str  = ""   # Telegram message_id
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
            "generated_assets":      self.generated_assets,
            "execution_record_id":   self.execution_record_id,
            "execution_records":     self.execution_records,
            "delivery_status":       self.delivery_status,
            "provider_message_id":   self.provider_message_id,
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

        # ── Step 7: Generate tailored assets (Batch 7) ────────────────────────
        from services.growth.asset_factory import generate_assets
        from services.growth.execution_record import persist as persist_records, get_primary_record

        asset_bundle  = generate_assets(decision.winner, research)
        exec_records  = persist_records(goal_id, decision.winner, asset_bundle)
        primary_rec   = get_primary_record(exec_records, decision.winner.channel)
        exec_rec_id   = primary_rec.record_id if primary_rec else ""

        log.info(
            f"[Pipeline] assets generated: {len(asset_bundle.assets)} assets, "
            f"primary_record_id={exec_rec_id}"
        )

        # ── Step 8: Persist goal + opportunities to DB ────────────────────────
        _persist(goal_id, raw_goal, domain, metric, tracks, scored, decision)

        # ── Step 9: Dispatch primary asset via Telegram (Batch 8) ─────────────
        dispatch_res = None
        if exec_rec_id:
            from services.growth.dispatcher import dispatch_record
            dispatch_res = dispatch_record(exec_rec_id)
            log.info(
                f"[Pipeline] dispatch record_id={exec_rec_id} "
                f"status={dispatch_res.delivery_status} "
                f"tg_id={dispatch_res.provider_message_id}"
            )

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
            generated_assets=asset_bundle.to_dict(),
            execution_record_id=exec_rec_id,
            execution_records=[r.to_dict() for r in exec_records],
            delivery_status=dispatch_res.delivery_status if dispatch_res else "skipped",
            provider_message_id=dispatch_res.provider_message_id if dispatch_res else "",
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
            generated_assets={},
            execution_record_id="",
            execution_records=[],
            delivery_status="skipped",
            provider_message_id="",
            success=False,
            error=str(e),
        )


# ── Reverse-lookup helpers ─────────────────────────────────────────────────────

def _reverse_potential(revenue_ils: int) -> str:
    """Map numeric ILS revenue back to high/medium/low category."""
    if revenue_ils >= 25_000:
        return "high"
    if revenue_ils >= 15_000:
        return "medium"
    return "low"


def _reverse_effort(effort_hours: int) -> str:
    """Map numeric effort hours back to low/medium/high category."""
    if effort_hours <= 10:
        return "low"
    if effort_hours <= 30:
        return "medium"
    return "high"


# ── DB persistence ─────────────────────────────────────────────────────────────

def _persist(
    goal_id:  str,
    raw_goal: str,
    domain:   str,
    metric:   str,
    tracks:   list,
    scored:   list,     # List[ScoredOpportunity]
    decision: object,   # CommitteeDecision
) -> None:
    """
    Write GoalModel + OpportunityModels with full numeric fields and committee data.
    Errors are logged, not raised — pipeline result is returned regardless.
    """
    try:
        from services.storage.db import get_session
        from services.storage.models.goal import GoalModel
        from services.storage.models.opportunity import OpportunityModel

        winner_id            = decision.winner.opp_id
        committee_json       = _json.dumps(decision.to_dict(), ensure_ascii=False)
        prioritized_json     = _json.dumps(decision.prioritized_actions, ensure_ascii=False)
        now_il               = _dt.datetime.now(_IL_TZ).isoformat()

        with get_session() as session:
            # ── Goal record ───────────────────────────────────────────────────
            session.add(GoalModel(
                id=goal_id,
                raw_goal=raw_goal,
                domain=domain,
                primary_metric=metric,
                status="active",
                goal_status="analyzed",
                tracks=tracks,
                committee_decision=committee_json,
                committee_winner_title=decision.winner.title,
                committee_reasoning=decision.reasoning,
                prioritized_actions_json=prioritized_json,
            ))

            # ── Opportunity records (bulk) ────────────────────────────────────
            for rank, scored_opp in enumerate(scored, start=1):
                session.add(OpportunityModel(
                    id=scored_opp.opp_id or str(uuid.uuid4()),
                    goal_id=goal_id,
                    track_id="",
                    title=scored_opp.title,
                    audience=scored_opp.audience,
                    channel=scored_opp.channel,
                    # Legacy string categories
                    potential=_reverse_potential(scored_opp.revenue_potential),
                    effort=_reverse_effort(scored_opp.effort),
                    # Full numeric metrics
                    normalized_score=scored_opp.normalized_score,
                    raw_score=scored_opp.raw_score,
                    success_probability=scored_opp.success_probability,
                    revenue_potential=scored_opp.revenue_potential,
                    effort_hours=scored_opp.effort,
                    # Committee fields
                    committee_rank=rank,
                    is_committee_winner=(scored_opp.opp_id == winner_id),
                    next_action="",
                    status="open",
                ))

        log.info(
            f"[Pipeline] persisted goal_id={goal_id} "
            f"opportunities={len(scored)} winner='{decision.winner.title}'"
        )
    except Exception as e:
        log.error(f"[Pipeline] DB persist failed goal_id={goal_id}: {e}", exc_info=True)
