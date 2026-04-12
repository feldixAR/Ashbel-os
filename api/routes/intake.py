"""
api/routes/intake.py — Direct file upload intake endpoint.

POST /api/intake/upload   — multipart file → parse → classify → preview
POST /api/intake/commit   — commit approved records to CRM
"""
from __future__ import annotations
import logging
from flask import Blueprint, request

from api.middleware import require_auth, log_request, ok, _error

bp  = Blueprint("intake", __name__)
log = logging.getLogger(__name__)


# ── Upload & Parse ────────────────────────────────────────────────────────────

@bp.route("/intake/upload", methods=["POST"])
@require_auth
@log_request
def upload():
    """
    Accept a multipart file upload. Parse it through document_intelligence,
    score each record deterministically, classify into groups, check duplicates.
    Returns a preview for client-side review before committing to CRM.
    """
    f = request.files.get("file")
    if not f:
        return _error("חסר קובץ — שלח multipart/form-data עם שדה 'file'", 400)

    file_name = f.filename or "upload"
    content   = f.read()
    if len(content) > 10 * 1024 * 1024:
        return _error("הקובץ גדול מדי — מקסימום 10MB", 400)

    try:
        from skills.document_intelligence import parse_document
        parsed = parse_document(content, file_name)
    except Exception as e:
        log.error(f"[Intake] parse failed: {e}")
        return _error(f"שגיאת ניתוח קובץ: {e}", 500)

    # Classify + score + check duplicates
    preview = _classify_records(parsed.records, file_name)

    return ok({
        "source_file":  file_name,
        "format":       parsed.format,
        "raw_count":    parsed.row_count,
        "records":      preview,
        "groups":       _group_summary(preview),
        "warnings":     parsed.warnings,
    })


# ── Commit approved records ───────────────────────────────────────────────────

@bp.route("/intake/commit", methods=["POST"])
@require_auth
@log_request
def commit():
    """
    Commit a list of approved records to the CRM.
    Body: {records: [{...}], source_file: "..."}
    Each record must have action != "skip" and action != "reject" to be imported.
    """
    data        = request.get_json(silent=True) or {}
    records     = data.get("records", [])
    source_file = data.get("source_file", "upload")

    if not records:
        return _error("אין רשומות לייבוא", 400)

    from engines.lead_acquisition_engine import process_inbound

    created = skipped = errors = 0
    lead_ids: list[str] = []

    for rec in records:
        action = rec.get("action", "approve")
        if action in ("skip", "reject"):
            skipped += 1
            continue
        try:
            lead_data = {
                "name":        rec.get("name", ""),
                "phone":       rec.get("phone", ""),
                "email":       rec.get("email", ""),
                "city":        rec.get("city", ""),
                "company":     rec.get("company", ""),
                "role":        rec.get("role", ""),
                "notes":       rec.get("notes", ""),
                "source_type": rec.get("source_type", "document_import"),
                "source_file": source_file,
                "segment":     rec.get("segment", ""),
                "is_inbound":  False,
            }
            lead_id = process_inbound(lead_data)
            if lead_id:
                lead_ids.append(lead_id)
                created += 1
            else:
                skipped += 1
        except Exception as e:
            log.error(f"[Intake] commit record failed: {e}")
            errors += 1

    return ok({
        "created":  created,
        "skipped":  skipped,
        "errors":   errors,
        "lead_ids": lead_ids,
        "message":  f"יובאו {created} לידים, דולגו {skipped}" + (f", שגיאות {errors}" if errors else ""),
    })


# ── Internal helpers ──────────────────────────────────────────────────────────

def _classify_records(records: list[dict], source_file: str) -> list[dict]:
    """Score, classify, and check duplicates for each parsed record."""
    from skills.lead_intelligence import normalize, enrich, score_lead
    from services.storage.repositories.lead_repo import LeadRepository

    repo = LeadRepository()
    out  = []

    for i, rec in enumerate(records):
        name  = (rec.get("name") or "").strip()
        phone = (rec.get("phone") or "").strip()
        email = (rec.get("email") or "").strip()

        # Duplicate check
        dup_id   = None
        dup_name = None
        if phone:
            existing = repo.find_by_phone(phone)
            if existing:
                dup_id   = existing.id
                dup_name = existing.name
        if not dup_id and email:
            existing = repo.find_by_email(email)
            if existing:
                dup_id   = existing.id
                dup_name = existing.name

        # Score (deterministic, no AI)
        try:
            lead     = normalize({**rec, "source_type": "document_import"})
            enriched = enrich(lead)
            scored   = score_lead(enriched)
            score    = scored.score
            next_act = scored.next_action
        except Exception:
            score    = 0
            next_act = "בדוק ידנית"

        # Classify
        if dup_id:
            group    = "duplicate"
            reason   = f"כבר קיים במערכת: {dup_name}"
            action   = "skip"
        elif not name and not phone and not email:
            group    = "missing_info"
            reason   = "חסר שם, טלפון ואימייל"
            action   = "skip"
        elif not name:
            group    = "missing_info"
            reason   = "חסר שם"
            action   = "review"
        elif not phone and not email:
            group    = "missing_info"
            reason   = "חסר פרטי קשר (טלפון/מייל)"
            action   = "review"
        elif score >= 60:
            group    = "relevant_now"
            reason   = f"ציון {score} — מומלץ לפעולה מיידית"
            action   = "approve"
        elif score >= 35:
            group    = "relevant_waiting"
            reason   = f"ציון {score} — רלוונטי, ממתין לתיעדוף"
            action   = "approve"
        else:
            group    = "not_relevant"
            reason   = f"ציון {score} — לא עמד בסף רלוונטיות"
            action   = "skip"

        out.append({
            **rec,
            "_idx":      i,
            "score":     score,
            "group":     group,
            "reason":    reason,
            "next_action": next_act,
            "action":    action,
            "dup_id":    dup_id,
            "dup_name":  dup_name,
        })

    return out


def _group_summary(records: list[dict]) -> dict:
    """Count records per group."""
    groups = {"relevant_now": 0, "relevant_waiting": 0,
              "not_relevant": 0, "missing_info": 0, "duplicate": 0}
    for r in records:
        g = r.get("group", "not_relevant")
        groups[g] = groups.get(g, 0) + 1
    return groups
