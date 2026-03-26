"""
Delivery routes — Axis 5 + Axis 6

POST /api/tasks/test-delivery   — Axis 5: one-off Telegram delivery proof
POST /api/tasks/run-scheduler-now — Axis 6: trigger the automated job immediately
"""

import logging
from flask import Blueprint
from api.middleware import require_auth, log_request, ok, _error

log = logging.getLogger(__name__)
bp  = Blueprint("delivery", __name__)


@bp.route("/tasks/test-delivery", methods=["POST"])
@require_auth
@log_request
def test_delivery():
    # 1. Generate today's plan
    try:
        from engines.outreach_engine import daily_outreach_summary
        summary = daily_outreach_summary()
    except Exception as e:
        log.error(f"[Delivery] daily_outreach_summary failed: {e}", exc_info=True)
        return _error(f"plan generation failed: {e}", 500)

    if not summary.top_priorities:
        return ok({
            "delivery_status": "skipped",
            "reason":          "no leads in top_priorities",
        })

    # 2. Take the highest-priority lead
    lead = summary.top_priorities[0]

    # 3. Format Telegram message
    message = (
        "🚀 *AshbelOS: Daily Action Plan*\n\n"
        f"*Lead:* {lead.lead_name}\n"
        f"*Reason:* {lead.reason}\n"
        f"*Action:* [Click to Chat]({lead.deep_link})"
    )

    # 4. Send via Telegram
    try:
        from services.telegram_service import telegram_service
        result = telegram_service.send(message)
    except Exception as e:
        log.error(f"[Delivery] telegram_service.send failed: {e}", exc_info=True)
        return _error(f"telegram send failed: {e}", 500)

    if not result.success:
        return ok({
            "delivery_status": "failed",
            "lead_name":       lead.lead_name,
            "error":           result.error,
        }, status=502)

    log.info(
        f"[Delivery] sent lead={lead.lead_name} "
        f"channel={lead.channel} message_id={result.message_id}"
    )
    return ok({
        "delivery_status": "success",
        "message_id":      result.message_id,
        "lead_name":       lead.lead_name,
        "channel":         lead.channel,
        "phone":           lead.phone,
        "urgency":         lead.urgency,
    })


@bp.route("/tasks/run-scheduler-now", methods=["POST"])
@require_auth
@log_request
def run_scheduler_now():
    """
    Axis 6 — trigger the automated telegram_delivery job immediately.
    Bypasses the idempotency guard (force=True) so it always runs on demand.
    Returns the same result dict the scheduled job would produce.
    """
    try:
        from scheduler.revenue_scheduler import _job_telegram_delivery
        result = _job_telegram_delivery(force=True)
    except Exception as e:
        log.error(f"[Delivery] run_scheduler_now failed: {e}", exc_info=True)
        return _error(f"scheduler job failed: {e}", 500)

    status_code = 200 if result.get("status") in ("success", "skipped") else 502
    return ok(result, status=status_code)
