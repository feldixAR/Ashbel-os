"""Safe document intake endpoints.

POST /api/intake/upload  - dry-run parse/classify/preview only
POST /api/intake/commit  - approved internal lead commit, never outreach
GET  /api/intake/reports - recent import reports
"""
from __future__ import annotations

import logging
from flask import Blueprint, request

from api.middleware import require_auth, log_request, ok, _error

bp = Blueprint("intake", __name__)
log = logging.getLogger(__name__)


@bp.route("/intake/upload", methods=["POST"])
@require_auth
@log_request
def upload():
    """Parse uploaded lead file and return a dry-run preview."""
    f = request.files.get("file")
    if not f:
        return _error("missing multipart file field 'file'", 400)

    file_name = f.filename or "upload"
    content = f.read()
    if len(content) > 10 * 1024 * 1024:
        return _error("file too large; max 10MB", 400)

    try:
        from skills.document_intelligence import parse_document
        parsed = parse_document(content, file_name)
    except Exception as e:
        log.error(f"[Intake] parse failed: {e}")
        return _error(f"parse failed: {e}", 500)

    preview = _classify_records(parsed.records, file_name)
    groups = _group_summary(preview)
    summary = _import_summary(preview)
    try:
        from services.storage.repositories.import_run_repo import ImportRunRepository
        import_run = ImportRunRepository().create_preview(
            source_file=file_name,
            source_format=parsed.format,
            raw_count=parsed.row_count,
            approved_count=summary["approved_count"],
            skipped_count=summary["skipped"],
            duplicate_count=summary["duplicates"],
            report={**summary, "groups": groups, "warnings": parsed.warnings},
        )
        import_run_id = import_run.id
    except Exception as e:
        log.error(f"[Intake] import run preview log failed: {e}")
        import_run_id = ""

    return ok({
        "source_file": file_name,
        "format": parsed.format,
        "raw_count": parsed.row_count,
        "approved_count": summary["approved_count"],
        "skipped": summary["skipped"],
        "duplicates": summary["duplicates"],
        "missing_phone_email": summary["missing_phone_email"],
        "hot_leads": summary["hot_leads"],
        "records": preview,
        "groups": groups,
        "summary": summary,
        "warnings": parsed.warnings,
        "import_run_id": import_run_id,
        "dry_run": True,
    })


@bp.route("/intake/commit", methods=["POST"])
@require_auth
@log_request
def commit():
    """Commit approved records only after formal import approval."""
    data = request.get_json(silent=True) or {}
    records = data.get("records", [])
    source_file = data.get("source_file", "upload")
    approval_id = data.get("approval_id") or ""
    import_run_id = data.get("import_run_id") or ""

    if not records:
        return _error("no records to import", 400)

    approved_records = [
        r for r in records
        if r.get("action", "approve") not in ("skip", "reject")
    ]
    if not approved_records:
        return _error("no approved records to import", 400)

    approval_check = _ensure_import_approval(
        approval_id=approval_id,
        source_file=source_file,
        records=approved_records,
        import_run_id=import_run_id,
    )
    if approval_check.get("pending"):
        return ok(approval_check, status=202)
    if approval_check.get("error"):
        return _error(approval_check["error"], approval_check.get("status", 400))

    from engines.lead_acquisition_engine import process_inbound

    created = skipped = errors = 0
    lead_ids: list[str] = []
    error_messages: list[str] = []
    import_batch = import_run_id or approval_check.get("approval_id") or source_file

    for rec in approved_records:
        try:
            lead_data = {
                "name": rec.get("name", ""),
                "phone": rec.get("phone", ""),
                "email": rec.get("email", ""),
                "city": rec.get("city", ""),
                "company": rec.get("company", ""),
                "role": rec.get("role", ""),
                "notes": rec.get("notes", ""),
                "source_type": rec.get("source_type", "document_import"),
                "source_file": source_file,
                "import_batch": import_batch,
                "segment": rec.get("segment", ""),
                "is_inbound": False,
                "work_type": rec.get("work_type", ""),
                "project_stage": rec.get("project_stage", ""),
                "estimated_value": rec.get("estimated_value", 0),
                "address": rec.get("address", ""),
                "decision_maker": rec.get("decision_maker", ""),
                "missing_photos": rec.get("missing_photos", True),
                "missing_plans": rec.get("missing_plans", True),
                "missing_measurements": rec.get("missing_measurements", True),
            }
            lead_id = process_inbound(lead_data)
            if lead_id:
                lead_ids.append(lead_id)
                created += 1
                _write_import_activity(lead_id, source_file, approval_check.get("approval_id", ""))
            else:
                skipped += 1
        except Exception as e:
            log.error(f"[Intake] commit record failed: {e}")
            errors += 1
            error_messages.append(str(e))

    summary = {
        **_import_summary(records),
        "created": created,
        "errors": errors,
        "lead_ids": lead_ids,
        "approval_id": approval_check.get("approval_id", ""),
        "import_run_id": import_run_id,
    }
    try:
        if import_run_id:
            from services.storage.repositories.import_run_repo import ImportRunRepository
            ImportRunRepository().mark_committed(
                import_run_id=import_run_id,
                approval_id=approval_check.get("approval_id", ""),
                created_count=created,
                skipped_count=skipped,
                error_count=errors,
                lead_ids=lead_ids,
                errors=error_messages,
                report=summary,
            )
    except Exception as e:
        log.error(f"[Intake] import run commit log failed: {e}")

    return ok({
        "created": created,
        "skipped": skipped,
        "errors": errors,
        "lead_ids": lead_ids,
        "approval_id": approval_check.get("approval_id", ""),
        "import_run_id": import_run_id,
        "report": summary,
        "sent_outreach": False,
        "message": f"imported {created} leads, skipped {skipped}" + (f", errors {errors}" if errors else ""),
    })


@bp.route("/intake/reports", methods=["GET"])
@require_auth
@log_request
def reports():
    """Recent import reports for the operator console."""
    from services.storage.repositories.import_run_repo import ImportRunRepository
    runs = ImportRunRepository().latest(limit=10)
    return ok({"reports": [_serialize_import_run(r) for r in runs], "total": len(runs)})


def _classify_records(records: list[dict], source_file: str) -> list[dict]:
    """Score, classify, check duplicates, and compute proposal readiness."""
    from skills.lead_intelligence import normalize, enrich, score_lead
    from services.storage.repositories.lead_repo import LeadRepository

    repo = LeadRepository()
    out = []
    for i, rec in enumerate(records):
        name = (rec.get("name") or "").strip()
        phone = (rec.get("phone") or "").strip()
        email = (rec.get("email") or "").strip()

        dup_id = None
        dup_name = None
        if phone:
            existing = repo.find_by_phone(phone)
            if existing:
                dup_id = existing.id
                dup_name = existing.name
        if not dup_id and email:
            existing = repo.find_by_email(email)
            if existing:
                dup_id = existing.id
                dup_name = existing.name

        try:
            lead = normalize({**rec, "source_type": "document_import"})
            enriched = enrich(lead)
            scored = score_lead(enriched)
            score = scored.score
            priority = scored.priority
            score_reason = " | ".join(scored.fit_reasons)
            next_act = scored.next_action
        except Exception:
            score = 0
            priority = "low"
            score_reason = ""
            next_act = "manual review"

        try:
            from skills.proposal_readiness import evaluate
            readiness = evaluate(rec)
        except Exception:
            readiness = {}

        if dup_id:
            group, reason, action = "duplicate", f"existing lead: {dup_name}", "skip"
        elif not name and not phone and not email:
            group, reason, action = "missing_info", "missing name, phone and email", "skip"
        elif not name:
            group, reason, action = "missing_info", "missing name", "review"
        elif not phone and not email:
            group, reason, action = "missing_info", "missing phone/email", "review"
        elif score >= 60:
            group, reason, action = "relevant_now", f"score {score}; immediate action recommended", "approve"
        elif score >= 35:
            group, reason, action = "relevant_waiting", f"score {score}; relevant but lower priority", "approve"
        else:
            group, reason, action = "not_relevant", f"score {score}; below relevance threshold", "skip"

        out.append({
            **rec,
            "_idx": i,
            "score": score,
            "priority": priority,
            "score_reason": score_reason,
            "group": group,
            "reason": reason,
            "next_action": next_act,
            "action": action,
            "dup_id": dup_id,
            "dup_name": dup_name,
            "source_file": source_file,
            "proposal_readiness": readiness,
            **_flatten_readiness(readiness),
        })
    return out


def _group_summary(records: list[dict]) -> dict:
    groups = {"relevant_now": 0, "relevant_waiting": 0,
              "not_relevant": 0, "missing_info": 0, "duplicate": 0}
    for r in records:
        g = r.get("group", "not_relevant")
        groups[g] = groups.get(g, 0) + 1
    return groups


def _import_summary(records: list[dict]) -> dict:
    return {
        "approved_count": sum(1 for r in records if r.get("action") == "approve"),
        "skipped": sum(1 for r in records if r.get("action") in ("skip", "reject")),
        "duplicates": sum(1 for r in records if r.get("group") == "duplicate"),
        "missing_phone_email": sum(1 for r in records if not r.get("phone") and not r.get("email")),
        "hot_leads": sum(1 for r in records if int(r.get("score") or 0) >= 70),
        "warnings": [],
    }


def _ensure_import_approval(approval_id: str, source_file: str,
                            records: list[dict], import_run_id: str) -> dict:
    from services.storage.repositories.approval_repo import ApprovalRepository
    repo = ApprovalRepository()
    if not approval_id:
        details = {
            "source_file": source_file,
            "import_run_id": import_run_id,
            "approved_count": len(records),
            "hot_leads": sum(1 for r in records if int(r.get("score") or 0) >= 70),
            "missing_phone_email": sum(1 for r in records if not r.get("phone") and not r.get("email")),
            "preview_only": False,
            "commit_never_sends_outreach": True,
        }
        approval = repo.create("import_commit", details, risk_level=2, requested_by="ui")
        try:
            if import_run_id:
                from services.storage.repositories.import_run_repo import ImportRunRepository
                ImportRunRepository().mark_pending_approval(import_run_id, approval.id)
        except Exception:
            pass
        return {
            "pending": True,
            "approval_required": True,
            "approval_id": approval.id,
            "message": "Import approval created. Approve it, then run commit with approval_id.",
        }

    approval = repo.get(approval_id)
    if not approval:
        return {"error": "approval_id not found", "status": 404}
    if approval.action != "import_commit":
        return {"error": "approval_id is not an import approval", "status": 400}
    if approval.status != "approved":
        return {"error": "import approval is not approved", "status": 403}
    details = approval.details or {}
    if details.get("source_file") and details.get("source_file") != source_file:
        return {"error": "approval_id does not match source_file", "status": 400}
    return {"approval_id": approval.id}


def _write_import_activity(lead_id: str, source_file: str, approval_id: str) -> None:
    try:
        from services.storage.db import get_session
        from services.storage.models.activity import ActivityModel
        with get_session() as s:
            s.add(ActivityModel(
                lead_id=lead_id,
                activity_type="note",
                direction="inbound",
                subject="Imported lead from file",
                notes=f"source_file={source_file}; approval_id={approval_id}; outreach_sent=false",
                outcome="completed",
                performed_by="operator",
            ))
    except Exception as e:
        log.error(f"[Intake] activity log failed: {e}")


def _flatten_readiness(readiness: dict) -> dict:
    if not readiness:
        return {}
    return {
        "ready_for_proposal": readiness.get("ready_for_proposal", False),
        "missing_photos": readiness.get("missing_photos", True),
        "missing_plans": readiness.get("missing_plans", True),
        "missing_measurements": readiness.get("missing_measurements", True),
        "missing_address": readiness.get("missing_address", True),
        "missing_decision_maker": readiness.get("missing_decision_maker", True),
        "missing_budget": readiness.get("missing_budget", True),
        "missing_project_stage": readiness.get("missing_project_stage", True),
        "proposal_followup_date": readiness.get("proposal_followup_date", ""),
        "proposal_metadata": readiness.get("proposal_metadata", {}),
    }


def _serialize_import_run(run) -> dict:
    return {
        "id": run.id,
        "source_file": run.source_file,
        "source_format": run.source_format,
        "status": run.status,
        "operator": run.operator,
        "approval_id": run.approval_id,
        "raw_count": run.raw_count,
        "approved_count": run.approved_count,
        "created_count": run.created_count,
        "skipped_count": run.skipped_count,
        "duplicate_count": run.duplicate_count,
        "error_count": run.error_count,
        "lead_ids": run.lead_ids or [],
        "errors": run.errors or [],
        "report": run.report or {},
        "created_at": str(run.created_at) if run.created_at else None,
        "committed_at": run.committed_at,
    }
