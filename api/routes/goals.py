"""
goals.py — /api/goals routes (Batch 6)
"""
import logging
from flask import Blueprint, request
from api.middleware import require_auth, log_request, ok, _error

log = logging.getLogger(__name__)
bp  = Blueprint("goals", __name__)


@bp.route("/goals", methods=["GET"])
@require_auth
@log_request
def list_goals():
    from services.storage.repositories.goal_repo import GoalRepository
    goals = GoalRepository().list_active()
    return ok({"goals": [g.to_dict() for g in goals], "total": len(goals)})


@bp.route("/goals/<goal_id>", methods=["GET"])
@require_auth
@log_request
def get_goal(goal_id: str):
    from services.storage.repositories.goal_repo import GoalRepository
    from services.storage.repositories.opportunity_repo import OpportunityRepository
    from services.storage.repositories.outreach_repo import OutreachRepository

    goal = GoalRepository().get(goal_id)
    if not goal:
        return _error(f"goal '{goal_id}' not found", 404)

    opps     = OpportunityRepository().list_by_goal(goal_id)
    outreach = OutreachRepository().list_by_goal(goal_id)

    return ok({
        "goal":          goal.to_dict(),
        "opportunities": [o.to_dict() for o in opps],
        "outreach":      [r.to_dict() for r in outreach],
        "stats": {
            "opportunities": len(opps),
            "outreach_sent": len([r for r in outreach if r.status == "sent"]),
            "replied":       len([r for r in outreach if r.status == "replied"]),
        },
    })


@bp.route("/goals/<goal_id>/opportunities", methods=["GET"])
@require_auth
@log_request
def list_opportunities(goal_id: str):
    from services.storage.repositories.opportunity_repo import OpportunityRepository
    opps = OpportunityRepository().list_by_goal(goal_id)
    return ok({"opportunities": [o.to_dict() for o in opps], "total": len(opps)})


@bp.route("/goals/<goal_id>/outreach", methods=["GET"])
@require_auth
@log_request
def list_outreach(goal_id: str):
    from services.storage.repositories.outreach_repo import OutreachRepository
    records = OutreachRepository().list_by_goal(goal_id)
    return ok({"outreach": [r.to_dict() for r in records], "total": len(records)})


@bp.route("/goals", methods=["POST"])
@require_auth
@log_request
def create_goal():
    """
    POST /api/goals
    Body: {"goal": "<raw goal text>"}
    Runs the full E2E growth pipeline and returns PipelineResult.
    """
    body = request.get_json(silent=True) or {}
    raw_goal = (body.get("objective") or body.get("goal") or "").strip()
    if not raw_goal:
        return _error("'objective' (or 'goal') field is required", 400)

    from services.growth.pipeline import run
    result = run(raw_goal)

    if not result.success:
        return _error(result.error or "pipeline failed", 500)

    cd = result.committee_decision or {}
    winner = cd.get("winner", {})

    return ok({
        # Core identifiers
        "goal_id":             result.goal_id,
        "goal_status":         "analyzed",
        # Winner summary (top-level for easy consumption)
        "winner": {
            "title":             winner.get("title"),
            "audience":          winner.get("audience"),
            "channel":           winner.get("channel"),
            "normalized_score":  winner.get("normalized_score"),
            "borda_score":       cd.get("winner_borda_score"),
            "reasoning":         cd.get("reasoning"),
        },
        # Primary generated asset (ready to use)
        "primary_asset":       (result.generated_assets or {}).get("primary_asset"),
        "execution_record_id": result.execution_record_id,
        # Full pipeline data
        "pipeline":            result.to_dict(),
    }, status=201)
