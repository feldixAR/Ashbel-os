"""
revenue_scheduler.py — Autonomous Revenue Scheduler (Batch 8/9)

Runs three recurring jobs:
  1. followup_job     — every 4h: send due follow-ups for all active goals
  2. daily_plan_job   — every morning 07:30 IL time: build & log daily revenue plan
  3. learning_job     — every night 23:00 IL time: run learning cycle

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
                ET.SYSTEM_EVENT,
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
        event_bus.publish(ET.SYSTEM_EVENT, payload=payload)
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
            ET.SYSTEM_EVENT,
            payload={"job": "learning_cycle", "summary": summary,
                     "ts": datetime.datetime.utcnow().isoformat()},
        )
        log.info(f"[Scheduler] learning_job: {summary}")
    except Exception as e:
        log.error(f"[Scheduler] learning_job crashed: {e}", exc_info=True)


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

            sched.start()
            _scheduler = sched
            _started   = True
            log.info("[Scheduler] started — followup/4h, daily_plan/07:30, learning/23:00")

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
