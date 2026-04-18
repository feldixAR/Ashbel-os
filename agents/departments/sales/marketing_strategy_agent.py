"""
MarketingStrategyAgent — Weekly marketing recommendations, campaign drafts, content calendar.

Handles:
    (marketing, weekly_recommendations)
    (marketing, campaign_draft)
    (marketing, marketing_analysis)
    (marketing, post_draft)
"""
import logging
from services.storage.models.task import TaskModel
from services.execution.executor  import ExecutionResult
from agents.base.base_agent       import BaseAgent

log = logging.getLogger(__name__)

_HANDLED = {
    ("marketing", "weekly_recommendations"),
    ("marketing", "campaign_draft"),
    ("marketing", "marketing_analysis"),
    ("marketing", "post_draft"),
    ("marketing", "generate_report"),
}


class MarketingStrategyAgent(BaseAgent):
    agent_id   = "builtin_marketing_strategy_agent_v1"
    name       = "Marketing Strategy Agent"
    department = "sales"
    version    = 1

    def can_handle(self, task_type: str, action: str) -> bool:
        return (task_type, action) in _HANDLED

    def execute(self, task: TaskModel) -> ExecutionResult:
        try:
            return self._run(task)
        except Exception as e:
            log.error(f"[MarketingStrategyAgent] error: {e}", exc_info=True)
            return ExecutionResult(success=False, message=f"שגיאה: {e}", output={"error": str(e)})

    def _run(self, task: TaskModel) -> ExecutionResult:
        from engines.marketing_engine import generate_weekly_plan, generate_marketing_report
        from config.business_registry import get_active_business
        profile = get_active_business()

        if task.action == "generate_report" or task.action == "marketing_analysis":
            report = generate_marketing_report(profile)
            return ExecutionResult(success=True, message="דוח שיווק נוצר",
                                   output={"report": report})

        if task.action == "post_draft":
            plan  = generate_weekly_plan(profile)
            posts = plan.post_drafts
            return ExecutionResult(success=True,
                                   message=f"הוכנו {len(posts)} טיוטות פוסטים",
                                   output={"posts": posts})

        if task.action == "campaign_draft":
            plan  = generate_weekly_plan(profile)
            ideas = plan.campaign_ideas
            return ExecutionResult(success=True,
                                   message=f"{len(ideas)} רעיונות קמפיין",
                                   output={"ideas": ideas, "seasonal": plan.seasonal_notes})

        # weekly_recommendations (default)
        plan = generate_weekly_plan(profile)
        recs = [{"category": r.category, "title": r.title, "body": r.body,
                  "channel": r.channel, "cta": r.cta} for r in plan.recommendations]
        return ExecutionResult(
            success=True,
            message=f"המלצות שיווק לשבוע — {len(recs)} פעולות מומלצות",
            output={
                "recommendations": recs,
                "campaign_ideas":  plan.campaign_ideas,
                "seasonal_notes":  plan.seasonal_notes,
                "post_drafts":     plan.post_drafts,
            },
        )
