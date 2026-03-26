"""
revenue_scheduler.py — Autonomous Revenue Scheduler (Batch 8/9 + Axis 6)

Runs four recurring jobs:
  1. followup_job          — every 4h: send due follow-ups for all active goals
  2. daily_plan_job        — every morning 07:30 IL time: build & log daily revenue plan
  3. learning_job          — every night 23:00 IL time: run learning cycle
  4. telegram_delivery_job — every morning 08:00 IL time: send top lead via Telegram

Design principles:
  - Each job is fully self-contained and wrapped in try/except — one failure never kills others.
  - Jobs log results to the event_bus so the system has an audit trail.
  - Scheduler starts in a background thread, non-blocking.
  - Safe to call start() multiple times (idempotent).
"""

import logging
import threading
import datetime

log = logging.getLogger(__name__)

# ── Idempotency guard for telegram_delivery_job ───────────────────────────────
_telegram_last_sent_date = ""   # ISO date string: "2026-03-26"
_telegram_lock = threading.Lock()

_scheduler = None
_started   = False
_lock      = threading.Lock()

# ── Job implementations ───────────────────────────────────────────────────────

def _job_followup():
    """Send due follow-ups for all active goals."""
    try:
        from services.storage.repositories.goal_repo import GoalRepository
        from engines.outreach_engine import outreach_engine
        from events.event_bus import event_bus
        import events.event_types as ET

        goals = GoalRepository().list_active()
        if not goals:
            log.debug("[Scheduler] followup_job: no active goals")
            return

        total_sent = 0
        for goal in goals:
            try:
                results = outreach_engine.run_followup_batch(goal.id)
                sent    = len(results) if results else 0
                total_sent += sent
                if sent:
                    log.info(f"[Scheduler] followup_job: goal={goal.id} sent={sent}")
            except Exception as e:
                log.error(f"[Scheduler] followup_job goal={goal.id} failed: {e}")

        if total_sent:
            event_bus.publish(
                ET.SCHEDULER_JOB_RAN,
                payload={"job": "followup", "sent": total_sent,
                         "ts": datetime.datetime.utcnow().isoformat()},
            )
        log.info(f"[Scheduler] followup_job complete — total sent: {total_sent}")
    except Exception as e:
        log.error(f"[Scheduler] followup_job crashed: {e}", exc_info=True)


def _job_daily_plan():
    """Build and log the daily revenue plan."""
    try:
        from engines.outreach_engine import outreach_engine
        from engines.revenue_engine   import revenue_snapshot
        from events.event_bus import event_bus
        import events.event_types as ET

        summary  = outreach_engine.build_daily_summary()
        snap     = revenue_snapshot()

        payload = {
            "job":          "daily_plan",
            "date":         datetime.date.today().isoformat(),
            "due_today":    getattr(summary, "total_due",  0),
            "hot_leads":    snap.hot_leads,
            "pipeline_est": snap.pipeline_value if hasattr(snap, "pipeline_value") else 0,
            "ts":           datetime.datetime.utcnow().isoformat(),
        }
        event_bus.publish(ET.SCHEDULER_JOB_RAN, payload=payload)
        log.info(f"[Scheduler] daily_plan_job: due={payload['due_today']} hot={payload['hot_leads']}")
    except Exception as e:
        log.error(f"[Scheduler] daily_plan_job crashed: {e}", exc_info=True)


def _job_learning_cycle():
    """Run the nightly learning & improvement cycle."""
    try:
        from engines.learning_engine import learning_engine
        from events.event_bus import event_bus
        import events.event_types as ET

        result = learning_engine.run_learning_cycle()
        summary = getattr(result, "cycle_summary", "learning cycle complete")
        event_bus.publish(
            ET.SCHEDULER_JOB_RAN,
            payload={"job": "learning_cycle", "summary": summary,
                     "ts": datetime.datetime.utcnow().isoformat()},
        )
        log.info(f"[Scheduler] learning_job: {summary}")
    except Exception as e:
        log.error(f"[Scheduler] learning_job crashed: {e}", exc_info=True)


def _job_telegram_delivery(force: bool = False) -> dict:
    """
    Axis 6 — automated Telegram delivery of top daily lead.

    Mirrors the exact flow from POST /api/tasks/test-delivery (Axis 5):
      daily_outreach_summary → top lead → format → telegram_service.send

    Idempotency: skips if already sent today (guards against scheduler misfires).
    Set force=True to bypass the guard (used by run-scheduler-now endpoint).

    Returns a result dict for observability / endpoint responses.
    """
    global _telegram_last_sent_date

    today = datetime.date.today().isoformat()

    # ── Idempotency check ─────────────────────────────────────────────────────
    with _telegram_lock:
        if not force and _telegram_last_sent_date == today:
            log.info(f"[Scheduler] telegram_delivery_job: already sent today ({today}), skipping")
            return {"status": "skipped", "reason": "already_sent_today", "date": today}

    log.info(f"[Scheduler] telegram_delivery_job: job_started date={today} force={force}")

    try:
        # ── 1. Generate plan ──────────────────────────────────────────────────
        from engines.outreach_engine import daily_outreach_summary
        summary = daily_outreach_summary()
        log.info(
            f"[Scheduler] telegram_delivery_job: plan_generated "
            f"leads={len(summary.top_priorities)} date={today}"
        )

        if not summary.top_priorities:
            log.info("[Scheduler] telegram_delivery_job: no leads in plan, skipping")
            return {"status": "skipped", "reason": "no_leads", "date": today}

        lead = summary.top_priorities[0]

        # ── 2. Format message (exact Axis 5 format) ───────────────────────────
        message = (
            "🚀 *AshbelOS: Daily Action Plan*\n\n"
            f"*Lead:* {lead.lead_name}\n"
            f"*Reason:* {lead.reason}\n"
            f"*Action:* [Click to Chat]({lead.deep_link})"
        )

        # ── 3. Send via Telegram ──────────────────────────────────────────────
        from services.telegram_service import telegram_service
        result = telegram_service.send(message)

        if result.success:
            with _telegram_lock:
                _telegram_last_sent_date = today
            log.info(
                f"[Scheduler] telegram_delivery_job: delivery_sent "
                f"lead={lead.lead_name} message_id={result.message_id} date={today}"
            )
            from events.event_bus import event_bus
            import events.event_types as ET
            event_bus.publish(
                ET.SCHEDULER_JOB_RAN,
                payload={
                    "job":        "telegram_delivery",
                    "date":       today,
                    "lead_name":  lead.lead_name,
                    "channel":    lead.channel,
                    "message_id": result.message_id,
                },
            )
            return {
                "status":     "success",
                "message_id": result.message_id,
                "lead_name":  lead.lead_name,
                "channel":    lead.channel,
                "date":       today,
            }

        log.error(
            f"[Scheduler] telegram_delivery_job: delivery_failed "
            f"lead={lead.lead_name} error={result.error}"
        )
        return {"status": "failed", "error": result.error, "lead_name": lead.lead_name}

    except Exception as e:
        log.error(f"[Scheduler] telegram_delivery_job crashed: {e}", exc_info=True)
        return {"status": "error", "error": str(e)}


def _job_startup_verification():
    """
    Axis 6 — one-shot verification job.
    Fires automatically 2 minutes after app startup.
    Proves APScheduler clock is ticking without any manual CURL.
    Calls the proven delivery flow with force=True (bypasses date idempotency).
    """
    log.info("[Scheduler] AUTOMATIC trigger: startup_verification_job starting...")
    result = _job_telegram_delivery(force=True)
    if result.get("status") == "success":
        log.info(
            f"[Scheduler] AUTOMATIC trigger: startup_verification_job SUCCESS — "
            f"message_id={result.get('message_id')} lead={result.get('lead_name')}"
        )
    elif result.get("status") == "skipped":
        log.info(
            f"[Scheduler] AUTOMATIC trigger: startup_verification_job SKIPPED — "
            f"reason={result.get('reason')}"
        )
    else:
        log.error(
            f"[Scheduler] AUTOMATIC trigger: startup_verification_job FAILED — "
            f"error={result.get('error')}"
        )


def _log_registered_jobs(sched) -> None:
    """Log all registered jobs and their next_run_time after scheduler starts."""
    jobs = sched.get_jobs()
    lines = []
    for job in jobs:
        nrt = job.next_run_time.strftime("%H:%M %Z") if job.next_run_time else "one-shot"
        lines.append(f"{job.id} @ {nrt}")
    log.info(f"[Scheduler] Registered Jobs: [{', '.join(lines)}]")


# ── Scheduler lifecycle ───────────────────────────────────────────────────────

def start():
    """Start the APScheduler background scheduler. Idempotent."""
    global _scheduler, _started
    with _lock:
        if _started:
            log.debug("[Scheduler] already running")
            return

        try:
            from apscheduler.schedulers.background import BackgroundScheduler
            import pytz

            il_tz = pytz.timezone("Asia/Jerusalem")
            sched = BackgroundScheduler(timezone=il_tz)

            # Follow-up every 4 hours
            sched.add_job(
                _job_followup,
                trigger="interval",
                hours=4,
                id="followup",
                replace_existing=True,
                misfire_grace_time=600,
            )

            # Daily plan every morning at 07:30 IL
            sched.add_job(
                _job_daily_plan,
                trigger="cron",
                hour=7, minute=30,
                id="daily_plan",
                replace_existing=True,
                misfire_grace_time=1800,
            )

            # Learning cycle every night at 23:00 IL
            sched.add_job(
                _job_learning_cycle,
                trigger="cron",
                hour=23, minute=0,
                id="learning_cycle",
                replace_existing=True,
                misfire_grace_time=1800,
            )

            # Telegram delivery every morning at 08:00 IL (Axis 6)
            sched.add_job(
                _job_telegram_delivery,
                trigger="cron",
                hour=8, minute=0,
                id="telegram_delivery",
                replace_existing=True,
                misfire_grace_time=1800,
            )

            # ── Axis 6 verification: one-shot job 2 min after startup ──────────
            # Fires once automatically to prove the scheduler clock is ticking.
            # Self-removes after execution (max_instances=1, no repeat trigger).
            _verify_at = datetime.datetime.now(il_tz) + datetime.timedelta(minutes=2)
            sched.add_job(
                _job_startup_verification,
                trigger="date",
                run_date=_verify_at,
                id="startup_verification",
                replace_existing=True,
            )

            sched.start()
            _scheduler = sched
            _started   = True

            # ── Registry log: all jobs + next_run_time ─────────────────────────
            _log_registered_jobs(sched)

        except ImportError:
            log.warning("[Scheduler] apscheduler not installed — autonomous jobs disabled")
        except Exception as e:
            log.error(f"[Scheduler] failed to start: {e}", exc_info=True)


def stop():
    """Graceful shutdown."""
    global _scheduler, _started
    with _lock:
        if _scheduler and _started:
            try:
                _scheduler.shutdown(wait=False)
            except Exception:
                pass
            _started = False
            log.info("[Scheduler] stopped")


def status() -> dict:
    """Return scheduler status for health endpoint."""
    return {
        "running": _started,
        "jobs": [j.id for j in _scheduler.get_jobs()] if _scheduler and _started else [],
    }
