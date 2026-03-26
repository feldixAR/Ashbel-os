"""
revenue_scheduler.py — Autonomous Revenue Scheduler (Batch 8/9 + Axis 6)

Runs five recurring jobs:
  1. followup_job              — every 4h: send due follow-ups for all active goals
  2. daily_plan_job            — every morning 07:30 IL time: build & log daily revenue plan
  3. learning_job              — every night 23:00 IL time: run learning cycle
  4. telegram_delivery_job     — every morning 08:00 IL time: send top lead via Telegram
  5. daily_learning_report_job — every evening 20:00 IL time: push learning digest via Telegram

Design principles:
  - Each job is fully self-contained and wrapped in try/except — one failure never kills others.
  - Jobs log results to the event_bus so the system has an audit trail.
  - Scheduler starts in a background thread, non-blocking.
  - Safe to call start() multiple times (idempotent).
"""

import logging
import os
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


def _job_daily_learning_report():
    """
    20:00 IL — Send daily learning KPI digest via Telegram.
    Calls services/notifications/telegram_service.send_daily_learning_report().
    Fails silently (missing env vars / API errors are logged, not raised).
    """
    try:
        from services.notifications.telegram_service import send_daily_learning_report
        result = send_daily_learning_report()
        if result["success"]:
            log.info(
                f"[Scheduler] daily_learning_report_job: sent "
                f"message_id={result['message_id']}"
            )
        else:
            log.warning(
                f"[Scheduler] daily_learning_report_job: not sent — "
                f"{result.get('error', 'unknown')}"
            )
    except Exception as e:
        log.error(f"[Scheduler] daily_learning_report_job crashed: {e}", exc_info=True)


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

    Idempotency: distributed DB lock via INSERT + IntegrityError.
    All Gunicorn workers race to INSERT a SentNotification row for
    (lead_id, delivery_date). The UNIQUE constraint ensures exactly one
    worker succeeds; the rest receive IntegrityError and skip delivery.

    force=True skips the DB lock (used by /api/tasks/run-scheduler-now).
    """
    import pytz
    from sqlalchemy.exc import IntegrityError

    pid   = os.getpid()
    il_tz = pytz.timezone("Asia/Jerusalem")
    today = datetime.datetime.now(il_tz).strftime("%Y-%m-%d")

    log.info(f"[Scheduler] telegram_delivery_job: job_started pid={pid} date={today}")

    try:
        # ── 1. Generate plan ──────────────────────────────────────────────────
        from engines.outreach_engine import daily_outreach_summary
        summary = daily_outreach_summary()
        log.info(
            f"[Scheduler] telegram_delivery_job: plan_generated "
            f"pid={pid} leads={len(summary.top_priorities)} date={today}"
        )

        if not summary.top_priorities:
            log.info(f"[Scheduler] telegram_delivery_job: no leads in plan pid={pid}, skipping")
            return {"status": "skipped", "reason": "no_leads", "date": today}

        lead = summary.top_priorities[0]

        # ── 2. Race INSERT — only the winning worker proceeds ─────────────────
        if not force:
            from services.storage.db import SessionLocal
            from services.storage.models.notification import SentNotificationModel
            import datetime as _dt

            today_date = datetime.datetime.now(il_tz).date()   # datetime.date object
            db = SessionLocal()
            try:
                db.add(SentNotificationModel(
                    lead_id=lead.lead_id,
                    delivery_date=today_date,
                    status="sent",
                ))
                db.commit()
                log.info(
                    f"[Scheduler] Worker {pid} - Lock acquired. "
                    f"Sending Telegram delivery..."
                )
            except IntegrityError:
                db.rollback()
                log.info(
                    f"[Scheduler] Worker {pid} - Duplicate detected. "
                    f"Skipping delivery for Lead {lead.lead_id}."
                )
                return {"status": "skipped", "reason": "already_sent_today",
                        "lead_id": lead.lead_id, "date": today}
            finally:
                db.close()

        # ── 3. Format message (exact Axis 5 format — unchanged) ───────────────
        message = (
            "🚀 *AshbelOS: Daily Action Plan*\n\n"
            f"*Lead:* {lead.lead_name}\n"
            f"*Reason:* {lead.reason}\n"
            f"*Action:* [Click to Chat]({lead.deep_link})"
        )

        # ── 4. Send via Telegram ──────────────────────────────────────────────
        from services.telegram_service import telegram_service
        result = telegram_service.send(message)

        if result.success:
            log.info(
                f"[Scheduler] telegram_delivery_job: delivery_sent "
                f"pid={pid} lead={lead.lead_name} message_id={result.message_id} date={today}"
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
            f"pid={pid} lead={lead.lead_name} error={result.error}"
        )
        return {"status": "failed", "error": result.error, "lead_name": lead.lead_name}

    except Exception as e:
        log.error(f"[Scheduler] telegram_delivery_job crashed pid={pid}: {e}", exc_info=True)
        return {"status": "error", "error": str(e)}


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

            # Daily learning report every evening at 20:00 IL (Batch 10.1)
            sched.add_job(
                _job_daily_learning_report,
                trigger="cron",
                hour=20, minute=0,
                id="daily_learning_report",
                replace_existing=True,
                misfire_grace_time=1800,
            )

            sched.start()
            _scheduler = sched
            _started   = True

            # ── Registry log: all jobs + next_run_time ─────────────────────────
            jobs  = sched.get_jobs()
            lines = [
                f"{j.id} @ {j.next_run_time.strftime('%H:%M %Z') if j.next_run_time else 'pending'}"
                for j in jobs
            ]
            log.info(f"[Scheduler] Registered Jobs: [{', '.join(lines)}]")

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
