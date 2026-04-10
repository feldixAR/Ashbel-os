"""
MaintenanceAgent — weekly health analysis + CLAUDE.md improvements.

Handles: task_type="executive", action="maintenance_report"
Runs: Sunday 07:00 IL via revenue_scheduler

Flow:
  analyze_sessions()       — read memory/sessions/ last 7 days (pure Python)
  propose_improvements()   — append to CLAUDE.md ## Session Updates
  build_health_report()    — Hebrew Telegram report
  run()                    — orchestrates all above
"""

import datetime
import logging
import pathlib
import re

from agents.base.base_agent       import BaseAgent
from services.storage.models.task import TaskModel
from services.execution.result    import ExecutionResult

log = logging.getLogger(__name__)

_REPO_ROOT = pathlib.Path(__file__).parent.parent.parent.parent


class MaintenanceAgent(BaseAgent):
    agent_id   = "builtin_maintenance_agent_v1"
    name       = "Maintenance Agent"
    department = "executive"
    version    = 1

    def can_handle(self, task_type: str, action: str) -> bool:
        return task_type == "executive" and action == "maintenance_report"

    def execute(self, task: TaskModel) -> ExecutionResult:
        try:
            return self._run_task(task)
        except Exception as e:
            log.error(f"[MaintenanceAgent] error: {e}", exc_info=True)
            return ExecutionResult(success=False, message=str(e),
                                   output={"error": str(e)})

    def _run_task(self, task: TaskModel) -> ExecutionResult:
        analysis  = self.analyze_sessions()
        claude_md = self.propose_improvements(analysis)
        report    = self.build_health_report(analysis)

        try:
            from services.telegram_service import telegram_service
            telegram_service.send(report)
        except Exception as e:
            log.warning(f"[MaintenanceAgent] telegram send failed: {e}")

        self._log_run(analysis)
        return ExecutionResult(
            success=True,
            message="דוח שבועי נשלח",
            output={"analysis": analysis, "report": report[:300]},
        )

    # ── Public methods ────────────────────────────────────────────────────────

    def analyze_sessions(self) -> dict:
        """Read memory/sessions/ last 7 days. Pure Python, 0 tokens."""
        sessions_dir = _REPO_ROOT / "memory" / "sessions"
        cutoff = datetime.date.today() - datetime.timedelta(days=7)

        failed_intents   = 0
        low_confidence   = 0
        repeated_errors  = {}
        expensive_agents = {}
        total_cost       = 0.0
        total_calls      = 0

        if sessions_dir.exists():
            for md_file in sorted(sessions_dir.glob("*.md")):
                try:
                    file_date = datetime.date.fromisoformat(md_file.stem)
                    if file_date < cutoff:
                        continue
                except ValueError:
                    continue

                try:
                    text = md_file.read_text(encoding="utf-8")
                except Exception:
                    continue

                # Parse cost lines: "cost_usd=0.00123"
                for m in re.finditer(r'cost_usd=([\d.]+)', text):
                    total_cost += float(m.group(1))
                # Parse call counts
                for m in re.finditer(r'calls=(\d+)', text):
                    total_calls += int(m.group(1))
                # Parse agent names
                for m in re.finditer(r'agent=(\S+)', text):
                    agent = m.group(1)
                    expensive_agents[agent] = expensive_agents.get(agent, 0) + 1
                # Simple error heuristic
                failed_intents  += text.count("UNKNOWN") + text.count("policy_block")
                low_confidence  += text.count("confidence=0")

        top3 = sorted(expensive_agents.items(), key=lambda x: x[1], reverse=True)[:3]

        return {
            "failed_intents":   failed_intents,
            "low_confidence":   low_confidence,
            "repeated_errors":  repeated_errors,
            "expensive_agents": dict(top3),
            "total_cost_usd":   round(total_cost, 4),
            "total_calls":      total_calls,
            "days_analyzed":    7,
        }

    def propose_improvements(self, analysis: dict) -> str:
        """Append ## Session Updates section to CLAUDE.md. Append-only."""
        today = datetime.date.today().isoformat()
        section = (
            f"\n## Session Updates — {today} (MaintenanceAgent)\n"
            f"- Failed intents (7d): {analysis['failed_intents']}\n"
            f"- Low confidence parses (7d): {analysis['low_confidence']}\n"
            f"- Total AI calls (7d): {analysis['total_calls']}\n"
            f"- Total token cost (7d): ${analysis['total_cost_usd']}\n"
            f"- Most active agents: {', '.join(analysis['expensive_agents'].keys()) or '—'}\n"
        )
        try:
            claude_md = _REPO_ROOT / "CLAUDE.md"
            with open(claude_md, "a", encoding="utf-8") as f:
                f.write(section)
            log.info("[MaintenanceAgent] appended to CLAUDE.md")
        except Exception as e:
            log.warning(f"[MaintenanceAgent] CLAUDE.md append failed: {e}")
        return section

    def build_health_report(self, analysis: dict) -> str:
        """Build Hebrew Telegram health report."""
        try:
            from routing.cost_tracker import cost_tracker
            cost_summary = cost_tracker.summary()
        except Exception:
            cost_summary = {}

        try:
            from services.storage.repositories.lead_repo import LeadRepository
            leads = LeadRepository().list_all()
            leads_total  = len(leads)
            leads_gmail  = sum(1 for l in leads if getattr(l, 'source', '') == 'gmail')
            leads_maps   = sum(1 for l in leads if getattr(l, 'source', '') == 'maps')
            leads_manual = leads_total - leads_gmail - leads_maps
        except Exception:
            leads_total = leads_gmail = leads_maps = leads_manual = 0

        today = datetime.date.today().isoformat()
        report = (
            f"📊 *דוח שבועי — AshbelOS*\n"
            f"📅 {today}\n\n"
            f"👥 *לידים*\n"
            f"  סה\"כ: {leads_total} | Gmail: {leads_gmail} | Maps: {leads_maps} | ידני: {leads_manual}\n\n"
            f"🤖 *סוכנים*\n"
            f"  קריאות AI (7 ימים): {analysis['total_calls']}\n"
            f"  עלות טוקנים: ${analysis['total_cost_usd']}\n"
            f"  סוכנים פעילים: {', '.join(analysis['expensive_agents'].keys()) or '—'}\n\n"
            f"⚠️ *שגיאות*\n"
            f"  כוונות לא זוהו: {analysis['failed_intents']}\n"
            f"  ביטחון נמוך: {analysis['low_confidence']}\n\n"
            f"✅ מערכת תקינה"
        )
        return report

    def _log_run(self, analysis: dict) -> None:
        try:
            sessions_dir = _REPO_ROOT / "memory" / "sessions"
            sessions_dir.mkdir(parents=True, exist_ok=True)
            today = datetime.date.today().isoformat()
            ts    = datetime.datetime.now(datetime.timezone.utc).strftime("%H:%M:%S")
            entry = (
                f"\n## {ts} UTC — MaintenanceAgent weekly run\n"
                f"- failed_intents={analysis['failed_intents']}"
                f" total_calls={analysis['total_calls']}"
                f" cost_usd={analysis['total_cost_usd']}\n"
            )
            with open(sessions_dir / f"{today}.md", "a", encoding="utf-8") as f:
                f.write(entry)
        except Exception:
            pass
