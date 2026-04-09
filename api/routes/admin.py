"""
api/routes/admin.py — Minimum viable admin + commercialization layer (Batch 10).

GET /api/admin/status   — active business config, DB counts, version, uptime
GET /api/admin/usage    — today's activity + outreach counts per type
"""
import datetime
import logging
import time as _time

from flask import Blueprint, request
from api.middleware import require_auth, ok, _error

log = logging.getLogger(__name__)
bp  = Blueprint("admin", __name__)

_START_TIME = _time.time()


@bp.route("/admin/status", methods=["GET"])
@require_auth
def admin_status():
    """
    GET /api/admin/status
    Returns: active business profile, DB record counts, version, uptime_seconds.
    """
    from config.business_registry import get_active_business
    from services.storage.db import get_session
    from services.storage.models.lead    import LeadModel
    from services.storage.models.deal    import DealModel
    from services.storage.models.outreach import OutreachModel
    from services.storage.models.approval import ApprovalModel

    biz = get_active_business()

    try:
        with get_session() as s:
            leads_total    = s.query(LeadModel).count()
            leads_active   = s.query(LeadModel).filter(
                LeadModel.status.notin_(["לא רלוונטי", "סגור"])
            ).count()
            deals_total    = s.query(DealModel).count()
            deals_active   = s.query(DealModel).filter(
                DealModel.stage.notin_(["won", "lost"])
            ).count()
            outreach_total = s.query(OutreachModel).count()
            approvals_pending = s.query(ApprovalModel).filter_by(status="pending").count()
    except Exception as e:
        log.error(f"[Admin] status DB query failed: {e}")
        leads_total = leads_active = deals_total = deals_active = \
            outreach_total = approvals_pending = -1

    uptime = int(_time.time() - _START_TIME)

    return ok({
        "business": {
            "id":             biz.business_id,
            "name":           biz.name,
            "domain":         biz.domain,
            "language":       biz.language,
            "currency":       biz.currency,
            "avg_deal_size":  biz.avg_deal_size,
            "primary_channel":biz.primary_channel,
        },
        "db": {
            "leads_total":       leads_total,
            "leads_active":      leads_active,
            "deals_total":       deals_total,
            "deals_active":      deals_active,
            "outreach_total":    outreach_total,
            "approvals_pending": approvals_pending,
        },
        "runtime": {
            "uptime_seconds": uptime,
            "timestamp_utc":  datetime.datetime.now(datetime.timezone.utc).isoformat(),
        },
    })


@bp.route("/admin/usage", methods=["GET"])
@require_auth
def admin_usage():
    """
    GET /api/admin/usage
    Returns today's execution counts: activities by type, outreach by channel,
    approvals resolved. Useful for SaaS usage metering and operator dashboards.
    """
    import datetime as _dt
    from services.storage.db import get_session
    from services.storage.models.activity import ActivityModel
    from services.storage.models.outreach  import OutreachModel
    from services.storage.models.approval  import ApprovalModel

    today = _dt.date.today().isoformat()  # YYYY-MM-DD

    try:
        with get_session() as s:
            # Activities today — count by activity_type
            acts = (
                s.query(ActivityModel.activity_type,
                        ActivityModel.id)
                .filter(ActivityModel.performed_at_il >= today)
                .all()
            )
            activity_counts: dict = {}
            for row in acts:
                activity_counts[row.activity_type] = \
                    activity_counts.get(row.activity_type, 0) + 1

            # Outreach today — count by channel
            out = (
                s.query(OutreachModel.channel, OutreachModel.id)
                .filter(OutreachModel.sent_at >= today)
                .all()
            )
            outreach_counts: dict = {}
            for row in out:
                outreach_counts[row.channel] = \
                    outreach_counts.get(row.channel, 0) + 1

            # Approvals resolved today
            approvals_resolved = (
                s.query(ApprovalModel)
                .filter(
                    ApprovalModel.status.in_(["approved", "denied"]),
                    ApprovalModel.resolved_at >= today,
                )
                .count()
            )

        total_actions = sum(activity_counts.values()) + sum(outreach_counts.values())

        return ok({
            "date":              today,
            "total_actions":     total_actions,
            "activities":        activity_counts,
            "outreach":          outreach_counts,
            "approvals_resolved": approvals_resolved,
        })

    except Exception as e:
        log.error(f"[Admin] usage query failed: {e}", exc_info=True)
        return _error(str(e), 500)
