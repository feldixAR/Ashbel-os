"""Authenticated internal source-review endpoints. No outreach or purchases."""
import os
from flask import Blueprint, request
from api.middleware import require_auth, ok, _error

bp = Blueprint("source_sync", __name__)


def _failure(exc):
    code = str(exc) if isinstance(exc, ValueError) else "source_unavailable"
    allowed = {
        "source_sync_disabled", "source_discovery_disabled", "source_spreadsheet_not_configured", "source_writer_not_configured",
        "source_verification_required", "preview_hash_mismatch", "preview_expired", "source_operation_not_found",
        "source_schema_mismatch", "source_range_exhausted_or_missing", "existing_duplicate_lead_ids",
        "operation_lease_missing", "source_verification_mismatch", "source_verification_expired",
        "specific_source_review_required", "candidate_not_found", "candidate_source_not_configured",
        "primary_source_unavailable", "invalid_candidate", "invalid_public_source_url", "invalid_entity_type",
    }
    if code not in allowed and not code.startswith("invalid_"):
        code = "source_unavailable"
    status = 503 if code in {"source_sync_disabled", "source_discovery_disabled", "source_spreadsheet_not_configured",
                             "source_writer_not_configured", "source_unavailable"} else 400
    return _error(code, status)


@bp.route("/source_sync/status", methods=["GET"])
@require_auth
def status():
    from services.integrations import source_sync as sync
    configured = bool(os.getenv("ASHBEL_SHEETS_WRITER_SERVICE_ACCOUNT_JSON", ""))
    operations = []
    if sync.enabled():
        try:
            operations = sync.recent_operations()
        except Exception as exc:
            return _failure(exc)
    return ok({"enabled": sync.enabled(), "writer_configured": configured, "operations": operations,
               "permissions": "append_existing_crm_only", "outreach_enabled": False})


@bp.route("/source_sync/preview", methods=["POST"])
@require_auth
def preview():
    from services.integrations.source_sync import prepare_append
    try:
        if request.content_length and request.content_length > 20000:
            return _error("candidate_too_large", 413)
        body = request.get_json(silent=True) or {}
        return ok(prepare_append(body.get("candidate")))
    except Exception as exc:
        return _failure(exc)


@bp.route("/source_sync/<operation_id>/commit", methods=["POST"])
@require_auth
def commit(operation_id):
    from services.integrations.source_sync import commit_append
    try:
        body = request.get_json(silent=True) or {}
        return ok(commit_append(operation_id, body.get("preview_hash")))
    except Exception as exc:
        return _failure(exc)


@bp.route("/source_sync/<operation_id>/reconcile", methods=["POST"])
@require_auth
def reconcile(operation_id):
    from services.integrations.source_sync import reconcile as readback
    try:
        return ok(readback(operation_id))
    except Exception as exc:
        return _failure(exc)


@bp.route("/source_discovery", methods=["GET"])
@require_auth
def discovery_status():
    from services.integrations import source_discovery as discovery
    try:
        return ok({"enabled": discovery.enabled(), "sources": discovery.sources(),
                   "candidates": discovery.list_candidates(), "crm_appended": 0,
                   "candidate_status": "unverified_requires_primary_source_review"})
    except Exception as exc:
        return _failure(exc)


@bp.route("/source_discovery/scan", methods=["POST"])
@require_auth
def scan():
    from services.integrations.source_discovery import scan_sources
    try:
        return ok(scan_sources())
    except Exception as exc:
        return _failure(exc)


@bp.route("/source_discovery/candidates/<task_id>/verify", methods=["POST"])
@require_auth
def verify_candidate(task_id):
    from services.integrations.source_discovery import verify_candidate as verify
    try:
        if request.content_length and request.content_length > 20000:
            return _error("candidate_too_large", 413)
        body = request.get_json(silent=True) or {}
        return ok(verify(task_id, body.get("candidate"), body.get("review_confirmed")))
    except Exception as exc:
        return _failure(exc)
