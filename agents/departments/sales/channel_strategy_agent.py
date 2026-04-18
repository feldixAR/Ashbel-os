"""
ChannelStrategyAgent — Selects best outreach channel and generates channel-ready draft.

Handles:
    (channel, select_channel)
    (channel, draft_for_channel)
    (channel, channel_status)
"""
import logging
from services.storage.models.task import TaskModel
from services.execution.executor  import ExecutionResult
from agents.base.base_agent       import BaseAgent

log = logging.getLogger(__name__)

_HANDLED = {
    ("channel", "select_channel"),
    ("channel", "draft_for_channel"),
    ("channel", "channel_status"),
    ("channel", "all_statuses"),
}


class ChannelStrategyAgent(BaseAgent):
    agent_id   = "builtin_channel_strategy_agent_v1"
    name       = "Channel Strategy Agent"
    department = "sales"
    version    = 1

    def can_handle(self, task_type: str, action: str) -> bool:
        return (task_type, action) in _HANDLED

    def execute(self, task: TaskModel) -> ExecutionResult:
        try:
            return self._run(task)
        except Exception as e:
            log.error(f"[ChannelStrategyAgent] error: {e}", exc_info=True)
            return ExecutionResult(success=False, message=f"שגיאה: {e}", output={"error": str(e)})

    def _run(self, task: TaskModel) -> ExecutionResult:
        from services.channels.channel_router import channel_router
        from config.business_registry import get_active_business
        params   = self._input_params(task)
        inp      = task.input_data or {}
        profile  = get_active_business()

        if task.action == "channel_status":
            channel = params.get("channel") or inp.get("channel", "whatsapp")
            status  = channel_router.status(channel)
            return ExecutionResult(success=True, message=f"סטטוס ערוץ {channel}: {status['status']}",
                                   output=status)

        if task.action == "all_statuses":
            statuses = channel_router.all_statuses()
            return ExecutionResult(success=True, message="סטטוס כל הערוצים",
                                   output={"channels": statuses})

        lead = params.get("lead") or {}
        if not lead:
            lead = {k: inp.get(k) for k in ("name","phone","email","linkedin_url") if inp.get(k)}

        if task.action == "select_channel":
            ch = channel_router.select(lead, profile)
            st = channel_router.status(ch)
            return ExecutionResult(success=True,
                                   message=f"ערוץ מומלץ: {ch} (סטטוס: {st['status']})",
                                   output={"channel": ch, "status": st})

        # draft_for_channel
        channel = params.get("channel") or inp.get("channel") or channel_router.select(lead, profile)
        body    = params.get("body") or inp.get("message") or inp.get("draft_body") or ""
        subject = params.get("subject") or inp.get("subject") or ""
        result  = channel_router.draft(channel, lead, body, subject, profile.name)
        msg = f"טיוטה ל-{channel}: {'מוכנה לשליחה ידנית' if result.status.value == 'readiness' else 'מוכנה לשליחה אוטומטית'}"
        return ExecutionResult(success=True, message=msg, output=result.to_dict())
