"""
reports.py — GET /api/reports/daily
"""
import logging
from flask import Blueprint
from api.middleware import require_auth, log_request, ok

log = logging.getLogger(__name__)
bp  = Blueprint("reports", __name__)


@bp.route("/reports/daily", methods=["GET"])
@require_auth
@log_request
def daily_report():
    from engines.reporting_engine import daily_summary, build_text_report
    summary = daily_summary()
    report  = build_text_report(summary)
    return ok({"summary": summary, "report_text": report})
