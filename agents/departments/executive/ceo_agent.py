"""
CEOAgent — handles strategy, analysis, and reporting tasks.

Handles:
    (strategy,      complex_reasoning)
    (analysis,      analyze_market)
    (summarization, generate_report)

Stage 3: structured template responses.
Stage 4: AI-powered via model_router.
"""

import logging
from services.storage.models.task  import TaskModel
from services.execution.executor   import ExecutionResult
from agents.base.base_agent        import BaseAgent

log = logging.getLogger(__name__)

_HANDLED = {
    ("strategy",      "complex_reasoning"),
    ("analysis",      "analyze_market"),
    ("summarization", "generate_report"),
}


class CEOAgent(BaseAgent):
    agent_id   = "builtin_ceo_agent_v1"
    name       = "CEO Agent"
    department = "executive"
    version    = 1

    def can_handle(self, task_type: str, action: str) -> bool:
        return (task_type, action) in _HANDLED

    def execute(self, task: TaskModel) -> ExecutionResult:
        try:
            return self._run(task)
        except Exception as e:
            log.error(f"[CEOAgent] error task={task.id}: {e}", exc_info=True)
            return ExecutionResult(success=False,
                                   message=f"שגיאה: {e}",
                                   output={"error": str(e)})

    def _run(self, task: TaskModel) -> ExecutionResult:
        if task.type == "summarization":
            return self._generate_report(task)
        params  = self._input_params(task)
        command = (task.input_data or {}).get("command", "")
        topic   = params.get("topic") or command
        return ExecutionResult(
            success=True,
            message="ניתוח אסטרטגי בוצע",
            output={
                "topic":    topic,
                "response": (f"ניתוח: {topic}\n"
                             f"• בשלב 4 יתווסף ניתוח מלא מבוסס Claude API."),
                "stage":    "stub_stage3",
            },
        )

    def _generate_report(self, task: TaskModel) -> ExecutionResult:
        from engines.reporting_engine import daily_summary, build_text_report
        summary = daily_summary()
        report  = build_text_report(summary)
        return ExecutionResult(
            success=True,
            message="דוח נוצר",
            output={"report": report, **summary},
        )
