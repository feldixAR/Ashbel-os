"""
ChiefOfStaffAgent — strategic planning coordinator.

Handles: task_type="executive", action="plan_action"

Flow:
  1. _local_compute(): timing + quota + scoring via policy_engine (0 tokens)
  2. Haiku: classify goal type + urgency
  3. Sonnet: draft action plan
  4. Opus: only if goal is "strategy" or high-complexity
  5. Log decision to memory/decisions/YYYY-MM-DD.md
"""

import datetime
import logging
import pathlib

from agents.base.base_agent       import BaseAgent
from services.storage.models.task import TaskModel
from services.execution.result    import ExecutionResult

log = logging.getLogger(__name__)


class ChiefOfStaffAgent(BaseAgent):
    agent_id   = "builtin_chief_of_staff_v1"
    name       = "Chief of Staff"
    department = "executive"
    version    = 1

    def can_handle(self, task_type: str, action: str) -> bool:
        return task_type == "executive" and action == "plan_action"

    def execute(self, task: TaskModel) -> ExecutionResult:
        try:
            return self._run(task)
        except Exception as e:
            log.error(f"[ChiefOfStaff] error task={task.id}: {e}", exc_info=True)
            return ExecutionResult(success=False,
                                   message=f"שגיאה בתכנון: {e}",
                                   output={"error": str(e)})

    def _run(self, task: TaskModel) -> ExecutionResult:
        params = self._input_params(task)
        goal   = self._safe_str(params.get("goal") or params.get("command") or
                                (task.input_data or {}).get("command", ""), "תכנן פעולות")

        # ── Step 1: local-first policy checks (0 tokens) ──────────────────
        local = self._local_compute(task)
        if local:
            return local

        # ── Step 2: Haiku — classify goal type + urgency (cheap) ──────────
        classification = self._classify_goal(goal)
        goal_type  = classification.get("type", "operational")
        urgency    = classification.get("urgency", "normal")

        # ── Step 3: choose model tier ──────────────────────────────────────
        if goal_type == "strategy" or urgency == "critical":
            priority = "quality"       # → Opus
            task_type_ai = "strategy"
        else:
            priority = "balanced"      # → Sonnet
            task_type_ai = "sales"

        # ── Step 4: build action plan ──────────────────────────────────────
        plan = self._build_plan(goal, goal_type, urgency, priority, task_type_ai)

        # ── Step 5: log decision ───────────────────────────────────────────
        self._log_decision(goal, goal_type, urgency, plan)

        return ExecutionResult(
            success=True,
            message=plan,
            output={
                "goal":       goal,
                "goal_type":  goal_type,
                "urgency":    urgency,
                "plan":       plan,
                "model_tier": "opus" if priority == "quality" else "sonnet",
            },
        )

    def _local_compute(self, task: TaskModel):
        """Check timing + quota before any AI. Returns ExecutionResult or None."""
        try:
            from services.policy.policy_engine import check_timing, check_quota
            timing = check_timing("general")
            if not timing["allowed"]:
                msg = f"⏰ {timing['reason']}. הפעולה הבאה אפשרית ב-{timing.get('next_slot','בקרוב')}."
                return ExecutionResult(success=False, message=msg,
                                       output={"policy_block": "timing", "reason": timing["reason"]})
        except Exception as e:
            log.debug(f"[ChiefOfStaff] policy check skipped: {e}")
        return None

    def _classify_goal(self, goal: str) -> dict:
        """Haiku: classify goal type + urgency. Cheap call."""
        try:
            system = (
                "You classify Hebrew business goals for an aluminum company (Ashbal Aluminum, Israel). "
                "Return JSON only: {\"type\": \"strategy|operational|outreach|crm\", "
                "\"urgency\": \"critical|high|normal|low\"}"
            )
            result = self._ai_call(
                task_type="classification",
                system_prompt=system,
                user_prompt=f"Goal: {goal}",
                priority="speed",
                max_tokens=60,
            )
            import json, re
            m = re.search(r'\{.*?\}', result, re.DOTALL)
            if m:
                return json.loads(m.group())
        except Exception as e:
            log.debug(f"[ChiefOfStaff] classify failed: {e}")
        return {"type": "operational", "urgency": "normal"}

    def _build_plan(self, goal: str, goal_type: str, urgency: str,
                    priority: str, task_type_ai: str) -> str:
        """Sonnet/Opus: build prioritized Hebrew action plan."""
        from config.business_knowledge import AUDIENCE_PLAYBOOK, ISRAELI_CULTURAL_RULES

        system = (
            "אתה Chief of Staff של אשבל אלומיניום — חברת אלומיניום ישראלית. "
            "אתה מתכנן פעולות עסקיות לשיפור מכירות, לידים, וקשרי לקוחות. "
            "ענה בעברית בלבד. תן תוכנית פעולה ממוקדת ב-3-5 צעדים ברורים. "
            "הצעד הראשון חייב להיות ניתן לביצוע עכשיו. "
            "אל תשתמש בקלישאות שיווקיות."
        )
        user = (
            f"יעד: {goal}\n"
            f"סוג: {goal_type} | דחיפות: {urgency}\n"
            f"תכנן 3-5 צעדים קונקרטיים לביצוע."
        )
        return self._ai_call(
            task_type=task_type_ai,
            system_prompt=system,
            user_prompt=user,
            priority=priority,
            max_tokens=500,
            use_cache=True,
        )

    def _log_decision(self, goal: str, goal_type: str, urgency: str, plan: str) -> None:
        """Append decision to memory/decisions/YYYY-MM-DD.md."""
        try:
            decisions_dir = pathlib.Path(__file__).parent.parent.parent.parent / "memory" / "decisions"
            decisions_dir.mkdir(parents=True, exist_ok=True)
            today = datetime.date.today().isoformat()
            log_path = decisions_dir / f"{today}.md"
            ts = datetime.datetime.now(datetime.timezone.utc).strftime("%H:%M:%S")
            entry = (
                f"\n## {ts} UTC — ChiefOfStaff\n"
                f"**יעד:** {goal}\n"
                f"**סוג:** {goal_type} | **דחיפות:** {urgency}\n\n"
                f"{plan}\n"
                f"\n---\n"
            )
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(entry)
        except Exception as e:
            log.warning(f"[ChiefOfStaff] decision log failed: {e}")
