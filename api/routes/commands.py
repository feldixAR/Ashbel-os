"""
POST /api/command

Accepts a natural-language command in Hebrew or English,
passes it to the orchestrator, and returns OrchestratorResult.

Request body:
    { "command": "תוסיף ליד יוסי כהן מתל אביב טלפון 0501234567" }

Response:
    {
      "success": true,
      "data": {
        "intent":         "add_lead",
        "message":        "ליד נוצר בהצלחה: יוסי כהן",
        "task_id":        "...",
        "trace_id":       "...",
        "needs_approval": false,
        "output":         { ... }
      }
    }
"""

import hashlib
import logging
import os
import re
from zoneinfo import ZoneInfo
from flask import Blueprint, request
from api.middleware import require_auth, log_request, ok, _error

log = logging.getLogger(__name__)
bp  = Blueprint("commands", __name__)


@bp.route("/command", methods=["POST"])
@require_auth
@log_request
def post_command():
    body = request.get_json(silent=True)
    if not isinstance(body, dict) or not isinstance(body.get("command"), str):
        return _error("field 'command' is required", 400)
    command = body["command"].strip()

    if body.get("mode") == "business_update":
        return _business_update(command, body.get("previous_event_id"), body.get("pending_message"))

    if not command:
        return _error("field 'command' is required", 400)

    from orchestration.orchestrator import orchestrator
    result = orchestrator.handle_command(command)

    return ok({
        "intent":         result.intent,
        "message":        result.message,
        "task_id":        result.task_id,
        "trace_id":       result.trace_id,
        "needs_approval": result.needs_approval,
        "approval_id":    result.approval_id,
        "output":         result.data,
        "error":          result.error,
    })


def _business_update(message, previous_event_id, pending_message, *,
                     source_ref="ashbelos:owner-console", delivery_id=None):
    from services.business_events import runtime
    from services.integrations.business_source import load_business_context

    message = " ".join(message.split())
    update = message
    if isinstance(pending_message, str) and len(message) <= 80:
        pending = " ".join(pending_message.split())
        if pending:
            update = pending
    if not message or len(update) > 1800 or "[ashbel-event:" in update.lower():
        return _error("כתוב עדכון עסקי באורך של עד 1,800 תווים.", 400)

    normalized = " " + _topic_words(message) + " "
    if re.match(r"^(?:ת?שלח|ת?פנה|ת?תקשר|ת?זמין|ת?תחייב|ת?שלם|ת?קנה)(?: |$)", normalized.strip()):
        return _error("הבקשה דורשת אישור מפורש לפנייה או להתחייבות. לא בוצעה פעולה.", 403)
    review = _review_intent(normalized) if update == message else None
    source = os.getenv("ASHBEL_CRM_WRITEBACK_SOURCE", "").strip()
    writer_enabled = os.getenv("ASHBEL_CRM_WRITEBACK_ENABLED", "").lower() == "true"
    if not (runtime.enabled() and source and (review or writer_enabled)):
        return _error("מסלול עדכוני העסק אינו זמין כרגע.", 503)

    context = load_business_context()
    if context.get("health") != "read_ok" or not context.get("snapshot_sha256"):
        return _error("לא ניתן לקרוא את ה־CRM כרגע. העדכון טרם נקלט.", 503)

    items = [item for item in context["actions"] if item["kind"] in {"customer", "supplier"}
             and item["disposition"] != "completed"]
    matches = []
    name_matches = []
    for item in items:
        parts = re.split(r"[|—–·]", item["subject"])
        aliases = {_topic_words(name) for name in [item["subject"], *parts]}
        if any(len(alias) >= 4 and f" {alias} " in normalized for alias in aliases):
            matches.append(item)
        elif item["kind"] == "customer" and len(parts) > 1:
            words = _topic_words(parts[0]).split()
            if len(words) > 1 and len(words[-1]) >= 3 and f" {words[-1]} " in normalized:
                name_matches.append(item)

    matches = matches or name_matches
    if not matches:
        # Use only supplier aliases already recorded by the trusted event pipeline.
        related = set()
        for event in runtime.recent_events(limit=50):
            if event["source"] != source or event["status"] != "analyzed":
                continue
            facts = event.get("facts") or {}
            subject = facts.get("work_item_subject")
            if not isinstance(subject, str):
                continue
            for field in ("manufacturing_supplier", "alternative_supplier"):
                name = facts.get(field)
                if isinstance(name, str):
                    alias = _topic_words(name.split("/", 1)[0])
                    if len(alias) >= 4 and f" {alias} " in normalized:
                        related.add(subject)
        matches = [item for item in items if item["subject"] in related]

    continuation = re.match(
        r"^(?:ו?בנוסף|ו?גם|ובינתיים|ועדכון נוסף|הוא|היא|הם|הן|לגבי זה|קיבלתי ממנו|קיבלתי ממנה)(?: |$)", normalized.strip()
    )
    followup_review = review == "deal" and (
        " איתו " in normalized or normalized.strip().removeprefix("ו") in {"מה הצעד הבא", "איך מתקדמים", "מה עושים עכשיו"}
    )
    if not matches and (continuation or followup_review):
        if isinstance(previous_event_id, str) and re.fullmatch(r"[0-9a-f-]{36}", previous_event_id):
            previous = runtime.get_event(previous_event_id) or {}
            result = previous.get("output") or {}
            writeback = result.get("source_writeback") or {}
            decision = result.get("ceo_decision") or {}
            audited_deal = (decision.get("review_scope") == "deal"
                            and (result.get("independent_auditor") or {}).get("passed") is True)
            if (previous.get("source") == source and previous.get("source_ref") == source_ref
                    and previous.get("status") == "analyzed" and (writeback.get("status") == "verified" or audited_deal)):
                subject = (previous.get("facts") or {}).get("work_item_subject")
                matches = [item for item in items if item["subject"] == subject]

    if review and len(matches) <= 1 and (review in {"portfolio", "deal_priorities"} or matches):
        return _business_review(runtime, source, context, matches[0] if matches else None, review, source_ref)
    if review or len(matches) != 1:
        return _error("על איזה פרויקט או ספק מדובר? אפשר לענות בשם שבו אתה משתמש בדרך כלל.", 422)

    item = matches[0]
    now = runtime.now()
    day = now.astimezone(ZoneInfo("Asia/Jerusalem")).date().isoformat()
    digest = hashlib.sha256(f"{day}\n{item['subject']}\n{update}".encode()).hexdigest()
    envelope = {
        "source": source,
        "source_event_id": delivery_id or f"console-update-{digest}",
        "source_ref": source_ref,
        "event_type": "supplier.updated" if item["kind"] == "supplier" else "customer.updated",
        "occurred_at": now.isoformat(),
        "facts": {"work_item_subject": item["subject"], "owner_update": update,
                  "external_contact_authorized": False},
    }
    try:
        receipt = runtime.ingest_event(envelope)
        event_id = receipt["id"]
        runtime.process_event(event_id, context=context)
        record = runtime.get_event(event_id)
    except Exception as exc:
        log.warning("Business update could not be confirmed: %s", type(exc).__name__)
        return _error("לא ניתן לאשר את השלמת העדכון כרגע. אפשר לנסות שוב עם אותה הודעה.", 503)

    output = (record or {}).get("output") or {}
    writeback = output.get("source_writeback") or {}
    audit = output.get("independent_auditor") or {}
    decision = output.get("ceo_decision") or {}
    if ((record or {}).get("status") != "analyzed" or writeback.get("status") != "verified"
            or audit.get("passed") is not True or output.get("external_execution") is not False or not decision.get("summary")):
        return _error(f"העדכון נקלט, אך הכתיבה ל־CRM טרם אומתה. מזהה האירוע: {event_id}", 409)

    next_step = ((decision.get("next_action") or {}).get("work_item") or {}).get("action")
    answer = f"מנכ״ל AshbelOS | {item['subject']}\n{decision['summary']}"
    if next_step:
        answer += f"\nהפעולה הפתוחה ב־CRM: {next_step}"
    answer += f"\nהעדכון נשמר ונקרא בחזרה ב־CRM ({writeback['cell']})."
    return ok({"message": answer, "intent": "business_update", "event_id": event_id,
               "trace_id": record["trace_id"], "crm_cell": writeback["cell"],
               "departments": sorted(output.get("departments", {})), "duplicate": receipt["duplicate"]})



def _review_intent(words):
    if re.search(r" (?:איזה|אילו) עסקאות ", words):
        return "deal_priorities"
    if re.search(r" תמונת (?:מצב |ה)?עסק | תמונת מצב | מצב העסק | מה פתוח | מה (?:המשימות|יש לי לעשות) (?:שלי )?להיום | מה (?:לקדם|כדאי לקדם) (?:היום|בעסק) ", words):
        return "portfolio"
    if re.match(
        r"^ו?(?:מה (?:כדאי לעשות|לעשות|עושים|המצב|מצב|הסטטוס|הצעד הבא|קורה עם)"
        r"|איך (?:לקדם|להתקדם|מתקדמים)|האם (?:לאשר|להתקשר|לסגור|לקדם)"
        r"|תן לי סטטוס|ת?קדם|תעדף)(?: |$)", words.strip()
    ):
        return "deal"
    return None


def _business_review(runtime, source, context, item, review, source_ref):
    snapshot = context["snapshot_sha256"]
    subject = item["subject"] if item else None
    now = runtime.now()
    day = now.astimezone(ZoneInfo("Asia/Jerusalem")).date().isoformat()
    scope = "deal" if item else review
    key = hashlib.sha256(f"v2\n{day}\n{snapshot}\n{scope}\n{subject}".encode()).hexdigest()
    if source_ref != "ashbelos:owner-console":
        key = hashlib.sha256(f"{source_ref}\n{key}".encode()).hexdigest()
    receipt = runtime.ingest_event({
        "source": source, "source_event_id": f"chat-review-{key}",
        "source_ref": source_ref, "event_type": "source.snapshot",
        "occurred_at": now.isoformat(),
        "facts": {"review_scope": scope, "work_item_subject": subject,
                  "snapshot_sha256": snapshot, "external_contact_authorized": False},
    })
    event_id = receipt["id"]
    runtime.process_event(event_id, context=context)
    event = runtime.get_event(event_id) or {}
    output = event.get("output") or {}
    decision = output.get("ceo_decision") or {}
    if (event.get("status") != "analyzed" or output.get("external_execution") is not False
            or (output.get("independent_auditor") or {}).get("passed") is not True
            or (output.get("source_writeback") or {}).get("status") != "not_attempted"
            or not decision.get("review_message")):
        return _error("בדיקת המנכ״ל טרם הושלמה. אפשר לנסות שוב.", 503)
    return ok({"message": decision["review_message"], "intent": "business_review",
               "context_event_id": event_id if item else None,
               "event_id": event_id, "trace_id": event["trace_id"],
               "departments": sorted(output.get("departments", {})), "duplicate": receipt["duplicate"]})


def _topic_words(text):
    return " ".join(re.findall(r"\w+", text.casefold().replace("_", " ")))
