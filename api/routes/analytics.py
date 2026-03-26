"""
api/routes/analytics.py — Batch 10: Analytics & Learning endpoints.

Endpoints:
    GET  /api/analytics/daily-learning   — KPI snapshot (24h + 7d windows)
    POST /api/analytics/recompute        — trigger full metrics recompute
    GET  /api/analytics/metrics          — raw PerformanceMetric rows
    GET  /api/analytics/metrics/<type>   — metrics filtered by dim_type
"""

import logging
from flask import Blueprint, request
from api.middleware import require_auth, log_request, ok, _error

log = logging.getLogger(__name__)
bp  = Blueprint("analytics", __name__)


@bp.route("/analytics/daily-learning", methods=["GET"])
@require_auth
@log_request
def daily_learning():
    """
    GET /api/analytics/daily-learning
    Returns top-converting channel + audience and revenue totals
    for the last 24h and 7d windows (Asia/Jerusalem).
    Reads from PerformanceMetric (snapshot) + live window queries.
    """
    from services.growth.learning_engine import revenue_window
    from services.storage.db import get_session
    from services.storage.models.analytics import PerformanceMetric

    # Live revenue windows
    r24h = revenue_window(hours=24)
    r7d  = revenue_window(hours=24 * 7)

    # Top performers from PerformanceMetric (sample_size >= 3)
    with get_session() as session:
        rows = (
            session.query(PerformanceMetric)
            .filter(PerformanceMetric.sample_size >= 3)
            .order_by(PerformanceMetric.conversion_rate.desc())
            .all()
        )
        all_metrics = [r.to_dict() for r in rows]

    channels  = [m for m in all_metrics if m["dim_type"] == "channel"]
    audiences = [m for m in all_metrics if m["dim_type"] == "audience"]

    top_channel  = channels[0]  if channels  else None
    top_audience = audiences[0] if audiences else None

    return ok({
        "computed_from":  "performance_metrics + live_outreach_records",
        "top_channel":    top_channel,
        "top_audience":   top_audience,
        "revenue": {
            "last_24h": r24h,
            "last_7d":  r7d,
        },
        "all_metrics_count": len(all_metrics),
    })


@bp.route("/analytics/recompute", methods=["POST"])
@require_auth
@log_request
def recompute():
    """
    POST /api/analytics/recompute
    Trigger a full learning metrics recomputation over WINDOW_DAYS (default 30d).
    Body (optional): {"window_days": 60}
    """
    body        = request.get_json(silent=True) or {}
    window_days = int(body.get("window_days", 30))

    if window_days < 1 or window_days > 365:
        return _error("window_days must be 1–365", 400)

    from services.growth.learning_engine import compute_lifecycle_metrics
    report = compute_lifecycle_metrics(window_days=window_days)

    return ok({
        "computed_at":    report.computed_at,
        "window_days":    report.window_days,
        "dimensions_updated": len(report.dimensions),
        "total_revenue":  report.total_revenue,
        "top_channel":    report.top_channel.to_dict() if report.top_channel else None,
        "top_audience":   report.top_audience.to_dict() if report.top_audience else None,
        "errors":         report.errors,
    })


@bp.route("/analytics/metrics", methods=["GET"])
@require_auth
@log_request
def list_metrics():
    """GET /api/analytics/metrics — return all PerformanceMetric rows."""
    from services.storage.db import get_session
    from services.storage.models.analytics import PerformanceMetric

    with get_session() as session:
        rows = (
            session.query(PerformanceMetric)
            .order_by(
                PerformanceMetric.dim_type,
                PerformanceMetric.conversion_rate.desc(),
            )
            .all()
        )
        data = [r.to_dict() for r in rows]

    return ok({"count": len(data), "metrics": data})


@bp.route("/analytics/metrics/<dim_type>", methods=["GET"])
@require_auth
@log_request
def metrics_by_type(dim_type: str):
    """GET /api/analytics/metrics/<dim_type> — channel | audience | opp_type."""
    valid = {"channel", "audience", "opp_type"}
    if dim_type not in valid:
        return _error(f"dim_type must be one of {sorted(valid)}", 400)

    from services.storage.db import get_session
    from services.storage.models.analytics import PerformanceMetric

    with get_session() as session:
        rows = (
            session.query(PerformanceMetric)
            .filter_by(dim_type=dim_type)
            .order_by(PerformanceMetric.conversion_rate.desc())
            .all()
        )
        data = [r.to_dict() for r in rows]

    return ok({"dim_type": dim_type, "count": len(data), "metrics": data})
