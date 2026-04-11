"""
LeadAcquisitionAgent — orchestrates the full lead acquisition pipeline.

Handles: task_type="acquisition" for all 4 actions:
  discover_leads   — goal → plan → signals → scored leads → work queue
  process_inbound  — inbound lead data → CRM + AI draft
  website_analysis — URL → audit + SEO + gaps + priority plan
  lead_ops_queue   — return current work queue from DB

AI usage:
  - Haiku  (cheap)    — pre-classify raw signals for Israeli relevance
  - Sonnet (balanced) — inbound response draft, lead briefing
  - Batch  — multi-signal classification via call_batch()

Local-first:
  - Empty signals → return discovery plan immediately (no AI)
  - Queue request with no pending leads → return counts (no AI)
"""

import logging
from services.storage.models.task  import TaskModel
from services.execution.result     import ExecutionResult
from agents.base.base_agent        import BaseAgent

log = logging.getLogger(__name__)

_CLASSIFY_SYSTEM = (
    "אתה מסייע לחברת אלומיניום ישראלית לזהות לידים רלוונטיים. "
    "ענה בעברית. "
    "קבל טקסט גולמי וסיין: YES אם מדובר בפוטנציאל לרכישת חלונות/דלתות/פרגולות אלומיניום, "
    "NO אחרת. ענה תחילה YES/NO ואז הסבר קצר עד 10 מילים."
)

_INBOUND_SYSTEM = (
    "אתה נציג מכירות של אשבל אלומיניום. "
    "כתוב תגובה ראשונית קצרה, אישית ומקצועית בעברית ללקוח שפנה. "
    "לא יותר מ-3 משפטים. אל תבטיח מחיר. הצע פגישה או ביקור."
)


class LeadAcquisitionAgent(BaseAgent):
    agent_id   = "builtin_lead_acquisition_v1"
    name       = "Lead Acquisition Agent"
    department = "sales"
    version    = 1

    def can_handle(self, task_type: str, action: str) -> bool:
        return task_type == "acquisition"

    def execute(self, task: TaskModel) -> ExecutionResult:
        try:
            local = self._local_compute(task)
            if local:
                return local
            action = task.action or ""
            p = self._input_params(task)
            if action == "discover_leads":
                return self._discover(task, p)
            if action == "process_inbound":
                return self._inbound(task, p)
            if action == "website_analysis":
                return self._website(task, p)
            if action == "lead_ops_queue":
                return self._queue(task, p)
            # default
            return self._discover(task, p)
        except Exception as e:
            log.error(f"[LeadAcquisitionAgent] task={task.id}: {e}", exc_info=True)
            return ExecutionResult(success=False, message=str(e), output={"error": str(e)})

    # ── Local-first ───────────────────────────────────────────────────────────

    def _local_compute(self, task: TaskModel):
        """Skip AI when there are no signals to process."""
        p = self._input_params(task)
        action = task.action or ""
        if action == "discover_leads":
            signals = p.get("signals") or []
            if not signals:
                # Return discovery plan without AI
                goal = p.get("goal") or "מציאת לקוחות לאלומיניום"
                try:
                    from engines.lead_acquisition_engine import run_acquisition
                    result = run_acquisition(goal=goal, signals=[])
                    return ExecutionResult(
                        success=True,
                        message=f"תוכנית גילוי מקורות עבור: {goal}",
                        output={
                            "goal":          result.goal,
                            "discovery_plan": result.discovery_plan,
                            "new_leads":     0,
                            "work_queue":    [],
                        },
                    )
                except Exception:
                    return None
        return None

    # ── Discover ──────────────────────────────────────────────────────────────

    def _discover(self, task: TaskModel, p: dict) -> ExecutionResult:
        from engines.lead_acquisition_engine import run_acquisition

        goal    = p.get("goal") or "מציאת לקוחות לאלומיניום"
        signals = p.get("signals") or []

        # AI pre-filter: classify signals for Israeli aluminum relevance (Haiku, batch)
        if signals:
            signals = self._classify_signals(signals)

        result = run_acquisition(goal=goal, signals=signals)

        msg = (
            f"גולה {result.new_leads} לידים חדשים "
            f"({result.duplicates} כפילויות) עבור: {goal}"
        )
        return ExecutionResult(
            success=True,
            message=msg,
            output={
                "goal":           result.goal,
                "total_discovered": result.total_discovered,
                "new_leads":      result.new_leads,
                "duplicates":     result.duplicates,
                "work_queue":     result.work_queue,
                "discovery_plan": result.discovery_plan,
                "session_id":     result.session_id,
                "errors":         result.errors,
            },
        )

    def _classify_signals(self, signals: list) -> list:
        """
        Use Haiku via call_batch() to pre-filter signals for Israeli aluminum relevance.
        Returns only signals classified as YES.
        Falls back to returning all signals if AI unavailable.
        """
        if len(signals) <= 2:
            return signals   # no batch overhead for ≤2 signals

        try:
            from routing.model_router import model_router
            from routing.cost_tracker import cost_tracker

            prompts = [
                str(s.get("text") or s.get("notes") or s.get("name") or "")[:300]
                for s in signals
            ]
            responses = model_router.call_batch(
                task_type="classification",
                system_prompt=_CLASSIFY_SYSTEM,
                user_prompts=prompts,
                priority="cheap",
                max_tokens=60,
            )
            cost_tracker.flush_to_session_log(self.agent_id)

            filtered = [
                s for s, r in zip(signals, responses)
                if str(r).strip().upper().startswith("YES")
            ]
            kept = len(filtered)
            total = len(signals)
            log.info(f"[LeadAcquisitionAgent] signal pre-filter: {kept}/{total} relevant")
            return filtered if filtered else signals   # never discard all
        except Exception as e:
            log.warning(f"[LeadAcquisitionAgent] classify_signals failed (non-critical): {e}")
            return signals

    # ── Inbound ───────────────────────────────────────────────────────────────

    def _inbound(self, task: TaskModel, p: dict) -> ExecutionResult:
        from engines.lead_acquisition_engine import process_inbound

        lead_data = {k: v for k, v in p.items()}
        lead_id   = process_inbound(lead_data)

        # AI-enhanced draft: personalised response using inbound message
        draft = self._ai_inbound_draft(lead_data)

        return ExecutionResult(
            success=True,
            message=f"ליד נכנס נקלט: {lead_data.get('name', 'לא ידוע')}",
            output={
                "lead_id": lead_id,
                "name":    lead_data.get("name"),
                "phone":   lead_data.get("phone"),
                "draft":   draft,
            },
        )

    def _ai_inbound_draft(self, lead_data: dict) -> str:
        """Generate an AI-personalised first response for an inbound lead."""
        name    = lead_data.get("name") or "לקוח"
        city    = lead_data.get("city") or ""
        message = lead_data.get("message") or lead_data.get("notes") or ""
        prompt  = (
            f"שם: {name}\n"
            f"עיר: {city}\n"
            f"הודעה: {message}\n\n"
            "כתוב תגובה ראשונית מותאמת אישית."
        )
        try:
            draft = self._ai_call(
                task_type="sales",
                system_prompt=_INBOUND_SYSTEM,
                user_prompt=prompt,
                priority="balanced",
                max_tokens=150,
                use_cache=True,
            )
            return draft
        except Exception as e:
            log.warning(f"[LeadAcquisitionAgent] ai_inbound_draft failed: {e}")
            return f"שלום {name}, תודה על פנייתך. נחזור אליך בהקדם. — אשבל אלומיניום"

    # ── Website ───────────────────────────────────────────────────────────────

    def _website(self, task: TaskModel, p: dict) -> ExecutionResult:
        from engines.lead_acquisition_engine import run_website_analysis

        url  = p.get("url") or ""
        html = p.get("html") or ""
        if not url:
            return ExecutionResult(
                success=False,
                message="חסר כתובת URL לניתוח",
                output={"error": "missing_url"},
            )

        r = run_website_analysis(url=url, html=html)
        return ExecutionResult(
            success=True,
            message=f"ניתוח אתר {url} — ציון: {r.audit_score}/100",
            output={
                "url":                 r.url,
                "audit_score":         r.audit_score,
                "lead_capture_score":  r.lead_capture_score,
                "top_recommendations": r.top_recommendations,
                "content_gaps":        r.content_gaps,
                "priority_plan":       r.priority_plan,
                "seo":                 r.seo,
            },
        )

    # ── Queue ─────────────────────────────────────────────────────────────────

    def _queue(self, task: TaskModel, p: dict) -> ExecutionResult:
        from services.storage.repositories.lead_repo import LeadRepository

        repo   = LeadRepository()
        leads  = repo.list_all(limit=50)
        status_filter = p.get("status")

        queue_items = []
        for lead in leads:
            if status_filter and getattr(lead, "status", None) != status_filter:
                continue
            queue_items.append({
                "id":              lead.id,
                "name":            lead.name,
                "phone":           lead.phone,
                "city":            lead.city,
                "status":          getattr(lead, "status", ""),
                "score":           getattr(lead, "score", 0),
                "outreach_action": getattr(lead, "outreach_action", ""),
                "is_inbound":      str(getattr(lead, "is_inbound", "false")).lower() in ("true", "1"),
                "source_type":     getattr(lead, "source_type", ""),
            })

        return ExecutionResult(
            success=True,
            message=f"תור לידים: {len(queue_items)} פריטים",
            output={"queue": queue_items, "count": len(queue_items)},
        )
