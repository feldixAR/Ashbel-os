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
        parsed = _apply_bonim_parser(parsed)
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
                "aluminum_intent": rec.get("aluminum_intent", ""),
                "construction_stage": rec.get("construction_stage", ""),
                "timing_window": rec.get("timing_window", ""),
                "business_reason": rec.get("business_reason", ""),
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


def _apply_bonim_parser(parsed):
    """Overlay Bonim Israel table/text normalization when that format is detected."""
    try:
        from skills import bonim_israel_parser as bonim
        records: list[dict] = []
        for table in getattr(parsed, "raw_tables", []) or []:
            if table and bonim.looks_like_headers([str(c or "") for c in (table[0] or [])]):
                records.extend(bonim.normalize_rows(table))
        text = "\n".join(getattr(parsed, "text_blocks", []) or [])
        if not records and bonim.looks_like_text(text):
            records.extend(bonim.normalize_text(text))
        if records:
            parsed.records = records
            parsed.row_count = len(records)
            if hasattr(parsed, "warnings"):
                parsed.warnings.append("bonim_israel_format_detected")
    except Exception as e:
        log.warning(f"[Intake] Bonim parser skipped: {e}")
        if hasattr(parsed, "warnings"):
            parsed.warnings.append(f"bonim parser skipped: {e}")
    return parsed


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
            legacy_score = scored.score
            priority = scored.priority
            score_reason = " | ".join(scored.fit_reasons)
            next_act = scored.next_action
        except Exception:
            legacy_score = 0
            priority = "low"
            score_reason = ""
            next_act = "manual review"

        try:
            from skills.proposal_readiness import evaluate
            readiness = evaluate(rec)
        except Exception:
            readiness = {}

        business = _business_score(rec, readiness)
        score = max(int(legacy_score or 0), int(business["score_total"]))
        business["score_total"] = score
        business["score"] = score

        if dup_id:
            group, reason, action = "duplicate", f"existing lead: {dup_name}", "skip"
        elif not name and not phone and not email:
            group, reason, action = "missing_info", "missing name, phone and email", "skip"
        elif not name:
            group, reason, action = "missing_info", "missing name", "review"
        elif not phone and not email:
            group, reason, action = "missing_info", "missing phone/email", "review"
        else:
            group, reason, action = _business_group_action(business)

        out.append({
            **rec,
            "_idx": i,
            "score": score,
            "score_total": score,
            "priority": priority,
            "score_reason": score_reason,
            "score_breakdown": business["score_breakdown"],
            "score_label": business["score_label"],
            "group": group,
            "reason": reason,
            "business_reason": business["business_reason"],
            "recommended_action": business["recommended_action"],
            "next_action": business["recommended_action"] or next_act,
            "next_action_date": business["next_action_date"],
            "timing_window": business["timing_window"],
            "urgency_level": business["urgency_level"],
            "aluminum_intent": business["aluminum_intent"],
            "aluminum_intent_label": business["aluminum_intent_label"],
            "construction_stage": business["construction_stage"],
            "construction_stage_label": business["construction_stage_label"],
            "work_type_detected": business["work_type_detected"],
            "confidence_level": business["confidence_level"],
            "missing_fields": _missing_fields(rec, readiness),
            "import_recommendation": action,
            "action": action,
            "dup_id": dup_id,
            "dup_name": dup_name,
            "source_file": source_file,
            "proposal_readiness": readiness,
            **_flatten_readiness(readiness),
        })
    return out


def _business_group_action(business: dict) -> tuple[str, str, str]:
    label = business.get("score_label", "skip")
    reason = business.get("business_reason", "")
    if label == "hot_now":
        return "hot_now", reason, "approve"
    if label == "clarify":
        return "clarify_aluminum", reason, "review"
    if label == "warm":
        return "relevant_waiting", reason, "approve"
    if label == "follow_up":
        return "follow_up_future", reason, "review"
    return "not_relevant", reason, "skip"


def _business_score(rec: dict, readiness: dict) -> dict:
    text = _lead_text(rec)
    intent, intent_label, intent_points, intent_conf = _classify_aluminum_intent(text)
    stage, stage_label, timing_window, stage_points = _classify_stage(text)
    contact_points = 15 if rec.get("phone") and rec.get("email") else 12 if rec.get("phone") else 8 if rec.get("email") else 0
    scope, scope_points = _classify_scope(text)
    geography_points = 5 if rec.get("city") or rec.get("address") else 0
    readiness_points = 5 if readiness.get("ready_for_proposal") else 0

    breakdown = {
        "intent": intent_points,
        "timing": stage_points,
        "contactability": contact_points,
        "scope": scope_points,
        "geography": geography_points,
        "readiness": readiness_points,
    }
    total = sum(breakdown.values())

    if intent == "explicit_aluminum" and stage in ("plaster", "late_skeleton", "mid_skeleton"):
        label = "hot_now"
        urgency = "high"
        action = "להתקשר היום ולבקש תכניות או תמונות לפתיחת הצעה"
        next_date = "today"
    elif intent == "all_fields" and stage in ("plaster", "late_skeleton"):
        label = "clarify"
        urgency = "high"
        action = "לברר היום האם האלומיניום כבר נסגר"
        next_date = "today"
    elif intent == "explicit_aluminum" and stage in ("early_skeleton", "foundations"):
        label = "follow_up"
        urgency = "medium"
        action = "לפתוח קשר עכשיו ולתזמן מעקב ל-30 עד 60 יום"
        next_date = "30-60_days"
    elif intent in ("explicit_aluminum", "adjacent_aluminum") and total >= 50:
        label = "warm"
        urgency = "medium"
        action = "ליצור קשר השבוע ולברר צורך מדויק באלומיניום"
        next_date = "this_week"
    elif intent == "all_fields":
        label = "clarify"
        urgency = "medium" if stage_points >= 16 else "low"
        action = "לשאול האם נדרש ספק אלומיניום ומה שלב ההחלטה"
        next_date = "this_week" if stage_points >= 16 else "future_follow_up"
    elif intent == "adjacent_aluminum":
        label = "warm" if stage_points >= 16 else "follow_up"
        urgency = "medium" if stage_points >= 16 else "low"
        action = "לבדוק התאמה לעבודות אלומיניום משלימות"
        next_date = "this_week" if stage_points >= 16 else "future_follow_up"
    else:
        label = "skip"
        urgency = "low"
        action = "לא לייבא אוטומטית ללא סימן לאלומיניום או צורך סמוך"
        next_date = "none"

    reason = _business_reason(intent_label, stage_label, timing_window, action)
    confidence = "high" if intent_conf == "high" and stage != "unknown" else "medium" if intent != "unknown" or stage != "unknown" else "low"

    return {
        "score_total": total,
        "score_label": label,
        "score_breakdown": breakdown,
        "aluminum_intent": intent,
        "aluminum_intent_label": intent_label,
        "construction_stage": stage,
        "construction_stage_label": stage_label,
        "timing_window": timing_window,
        "urgency_level": urgency,
        "business_reason": reason,
        "recommended_action": action,
        "next_action_date": next_date,
        "work_type_detected": scope,
        "confidence_level": confidence,
    }


def _lead_text(rec: dict) -> str:
    return " ".join(str(rec.get(k, "") or "") for k in (
        "name", "city", "address", "notes", "work_type", "project_stage", "segment", "role", "company"
    ))


def _classify_aluminum_intent(text: str) -> tuple[str, str, int, str]:
    t = text or ""
    if "אלומיניום" in t or "בלגי" in t:
        return "explicit_aluminum", "ביקש אלומיניום במפורש", 35, "high"
    if any(x in t for x in ("כל התחומים", "כל הספקים", "כל בעלי המקצוע", "כל העבודות", "כללי")):
        return "all_fields", "ביקש הצעות בכל התחומים", 18, "medium"
    if any(x in t for x in ("פרגולה", "פרגולות", "שער", "שערים", "גדר", "גדרות", "מעקה", "מעקות", "ויטרינה", "ויטרינות", "חלון", "חלונות", "דלת", "דלתות")):
        return "adjacent_aluminum", "תחום סמוך לאלומיניום", 14, "medium"
    if t.strip():
        return "no_aluminum", "לא זוהתה בקשת אלומיניום", 0, "medium"
    return "unknown", "לא זוהה תחום", 0, "low"


def _classify_stage(text: str) -> tuple[str, str, str, int]:
    t = text or ""
    if "טיח" in t:
        return "plaster", "טיח", "עכשיו", 30
    if "גמר" in t or "עבודות גמר" in t:
        return "finishing", "גמר", "בירור מיידי", 25
    if "סוף שלד" in t or "לקראת סיום שלד" in t:
        return "late_skeleton", "סוף שלד", "עכשיו", 27
    if "אמצע שלד" in t or "במהלך שלד" in t:
        return "mid_skeleton", "אמצע שלד", "השבוע", 23
    if "תחילת שלד" in t or "שלד" in t:
        return "early_skeleton", "תחילת שלד", "מעקב קרוב", 16
    if "יסודות" in t or "כלונס" in t:
        return "foundations", "יסודות", "מעקב עתידי", 8
    if "תכנון" in t or "היתר" in t or "גרמושקה" in t:
        return "planning", "תכנון", "כמה חודשים", 5
    return "unknown", "שלב לא מזוהה", "בדיקה ידנית", 0


def _classify_scope(text: str) -> tuple[str, int]:
    t = text or ""
    if "אלומיניום" in t and any(x in t for x in ("כל", "בית", "וילה", "חלונות", "דלתות")):
        return "חבילת אלומיניום לבית", 10
    if any(x in t for x in ("חלונות", "דלתות", "ויטרינות", "בלגי")):
        return "חלונות ודלתות", 8
    if any(x in t for x in ("פרגולה", "שער", "גדר", "מעקה")):
        return "עבודת אלומיניום משלימה", 5
    return "לא זוהה היקף עבודה", 0


def _business_reason(intent_label: str, stage_label: str, timing_window: str, action: str) -> str:
    return f"{intent_label}. שלב הבנייה: {stage_label}. חלון פעולה: {timing_window}. פעולה מומלצת: {action}."


def _missing_fields(rec: dict, readiness: dict) -> list[str]:
    missing: list[str] = []
    if not rec.get("phone") and not rec.get("email"):
        missing.append("טלפון או מייל")
    if readiness.get("missing_plans", True):
        missing.append("תכניות")
    if readiness.get("missing_measurements", True):
        missing.append("מידות")
    if readiness.get("missing_photos", True):
        missing.append("תמונות")
    if readiness.get("missing_project_stage", True) and not rec.get("project_stage"):
        missing.append("שלב פרויקט")
    return missing


def _group_summary(records: list[dict]) -> dict:
    groups = {
        "hot_now": 0,
        "clarify_aluminum": 0,
        "follow_up_future": 0,
        "relevant_waiting": 0,
        "not_relevant": 0,
        "missing_info": 0,
        "duplicate": 0,
    }
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
        "hot_leads": sum(1 for r in records if r.get("group") == "hot_now" or int(r.get("score") or 0) >= 70),
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
            "hot_leads": sum(1 for r in records if r.get("group") == "hot_now" or int(r.get("score") or 0) >= 70),
            "missing_phone_email": sum(1 for r in records if not r.get("phone") and not r.get("email")),
            "preview_only": False,
            "commit_never_sends_outreach": True,
            "approval_copy": "אישור זה מכניס לידים נבחרים למערכת בלבד. הוא לא שולח WhatsApp, לא שולח Email ולא פונה ללקוחות.",
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
