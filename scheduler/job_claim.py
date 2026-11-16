"""Database-backed claims shared by all workers and retained across restarts.

At most one worker may invoke a job for an occurrence. A crashed worker leaves
its claim for operator investigation; automatic replay could duplicate an
external side effect. ``returned`` means only that the callback returned: jobs
may handle their own errors and this wrapper does not invent success.
"""
import datetime
import logging

log = logging.getLogger(__name__)
_INTERVAL_SECONDS = {'followup': 4 * 3600, 'gmail_scan': 30 * 60}


def occurrence_slot(job_id, now=None):
    now = now or datetime.datetime.now(datetime.timezone.utc)
    if now.tzinfo is None:
        raise ValueError('scheduled time must include a timezone')
    if job_id in _INTERVAL_SECONDS:
        seconds = _INTERVAL_SECONDS[job_id]
        return str(int(now.timestamp()) // seconds)
    from zoneinfo import ZoneInfo
    # Daily/weekly cron jobs run once on their local scheduled calendar date.
    return now.astimezone(ZoneInfo('Asia/Jerusalem')).date().isoformat()


def run_scheduled_once(job_id, callback, now=None):
    from sqlalchemy.exc import IntegrityError
    from services.storage.db import get_session
    from services.storage.models.scheduler_run import SchedulerRunModel

    slot = occurrence_slot(job_id, now)
    try:
        with get_session() as session:
            session.add(SchedulerRunModel(job_id=job_id, slot=slot, status='claimed'))
            session.flush()
    except IntegrityError:
        log.info('[Scheduler] occurrence already claimed job=%s slot=%s', job_id, slot)
        return {'status': 'skipped', 'reason': 'already_claimed', 'job_id': job_id, 'slot': slot}
    except Exception:
        # Never run an unclaimed job when the coordination database is unavailable.
        log.exception('[Scheduler] claim unavailable job=%s slot=%s', job_id, slot)
        return {'status': 'blocked', 'reason': 'claim_unavailable', 'job_id': job_id, 'slot': slot}

    status, error = 'returned', None
    try:
        return callback()
    except Exception as exc:
        status, error = 'failed', type(exc).__name__
        raise
    finally:
        try:
            with get_session() as session:
                row = session.get(SchedulerRunModel, (job_id, slot))
                row.status = status
                row.error = error
                row.finished_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
        except Exception:
            log.exception('[Scheduler] claim result unavailable job=%s slot=%s', job_id, slot)


def recent_claims(limit=20):
    from services.storage.db import get_session
    from services.storage.models.scheduler_run import SchedulerRunModel
    with get_session() as session:
        rows = (session.query(SchedulerRunModel)
                .order_by(SchedulerRunModel.created_at.desc()).limit(limit).all())
        return [{'job_id': row.job_id, 'slot': row.slot, 'status': row.status,
                 'finished_at': row.finished_at} for row in rows]
