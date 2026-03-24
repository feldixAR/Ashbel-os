"""
BuildManagerAgent — manages system build requests.

Handles:
    (agent_build, create_agent)
    (development, roadmap)
    (development, gap_analysis)
    (development, batch_status)
"""

import logging

from services.storage.models.task import TaskModel
from services.execution.result  import ExecutionResult
from agents.base.base_agent import BaseAgent

log = logging.getLogger(__name__)

_HANDLED = {
    ("agent_build", "create_agent"),
    ("development", "roadmap"),
    ("development", "gap_analysis"),
    ("development", "batch_status"),
}


class BuildManagerAgent(BaseAgent):
    agent_id = "builtin_build_manager_agent_v1"
    name = "Build Manager Agent"
    department = "executive"
    version = 2

    _BATCHES = [
        {
            "id": "batch_1",
            "name": "Conversational Interface",
            "status": "partial",
            "goal": "הבנת שפה טבעית עסקית",
            "next_step": "expand_free_text_understanding",
        },
        {
            "id": "batch_2",
            "name": "Action Draft Layer",
            "status": "implemented",
            "goal": "הכנת טיוטות הודעה, פגישה, דשבורד",
            "next_step": "connect_real_execution_later",
        },
        {
            "id": "batch_3",
            "name": "Development Control Layer",
            "status": "in_progress",
            "goal": "ניהול roadmap, gaps וסטטוס batches",
            "next_step": "expose_roadmap_and_gap_commands",
        },
        {
            "id": "batch_4",
            "name": "Dynamic Agent Factory",
            "status": "partial",
            "goal": "יצירה ורישום דינמי של סוכנים",
            "next_step": "persist_dynamic_agents",
        },
        {
            "id": "batch_5",
            "name": "Revenue Optimization Layer",
            "status": "planned",
            "goal": "זיהוי הזדמנויות והמלצות להכנסות",
            "next_step": "build_revenue_agent",
        },
        {
            "id": "batch_6",
            "name": "External Integrations",
            "status": "planned",
            "goal": "WhatsApp, Calendar, Contacts",
            "next_step": "connect_real_channels",
        },
    ]

    _GAPS = [
        "אין עדיין פתיחה אמיתית של WhatsApp",
        "אין עדיין יצירה אמיתית של אירועי יומן",
        "אין עדיין עדכון אמיתי של מסך הבית",
        "אין עדיין חיבור לאנשי קשר אמיתיים",
        "אין עדיין Revenue layer פעיל",
        "אין עדיין Agent Factory דינמי מלא",
    ]

    def can_handle(self, task_type: str, action: str) -> bool:
        return (task_type, action) in _HANDLED

    def execute(self, task: TaskModel) -> ExecutionResult:
        try:
            return self._run(task)
        except Exception as e:
            log.error(f"[BuildManagerAgent] error task={task.id}: {e}", exc_info=True)
            return ExecutionResult(
                success=False,
                message=f"שגיאה בניהול הפיתוח: {e}",
                output={"error": str(e)},
            )

    def _run(self, task: TaskModel) -> ExecutionResult:
        if task.type == "development" and task.action == "roadmap":
            return self._roadmap()

        if task.type == "development" and task.action == "gap_analysis":
            return self._gap_analysis()

        if task.type == "development" and task.action == "batch_status":
            return self._batch_status()

        return self._create_agent_spec(task)

    def _create_agent_spec(self, task: TaskModel) -> ExecutionResult:
        params = self._input_params(task)
        command = (task.input_data or {}).get("command", "").strip()

        requested_agent = (
            params.get("agent_name")
            or params.get("name")
            or "Executive Assistant Agent"
        )

        build_spec = {
            "requested_agent": requested_agent,
            "goal": command or "יצירת סוכן חדש במערכת",
            "stage": "build_spec_only",
            "status": "planned",
            "next_step": "create_agent_code_and_register",
            "files_to_create": [
                f"agents/departments/executive/{self._slugify(requested_agent)}.py"
            ],
            "files_to_update": [
                "agents/base/agent_registry.py",
                "orchestration/orchestrator.py",
            ],
            "required_capabilities": [
                "intent_understanding",
                "action_planning",
                "draft_generation",
                "approval_flow",
            ],
        }

        return ExecutionResult(
            success=True,
            message=f"נוצר מפרט בנייה עבור {requested_agent}",
            output=build_spec,
        )

    def _roadmap(self) -> ExecutionResult:
        return ExecutionResult(
            success=True,
            message="Roadmap הפיתוח מוכן",
            output={
                "status": "roadmap_ready",
                "current_focus": "Development Control Layer",
                "next_build_batch": "Dynamic Agent Factory",
                "batches": self._BATCHES,
            },
        )

    def _gap_analysis(self) -> ExecutionResult:
        return ExecutionResult(
            success=True,
            message="Gap analysis מוכן",
            output={
                "status": "gap_analysis_ready",
                "gaps": self._GAPS,
                "next_step": "build_dynamic_factory_then_revenue_layer",
            },
        )

    def _batch_status(self) -> ExecutionResult:
        return ExecutionResult(
            success=True,
            message="סטטוס batches מוכן",
            output={
                "status": "batch_status_ready",
                "batches": self._BATCHES,
            },
        )

    def _slugify(self, text: str) -> str:
        clean = "".join(ch.lower() if ch.isalnum() else "_" for ch in text)
        while "__" in clean:
            clean = clean.replace("__", "_")
        return clean.strip("_") or "new_agent"
