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
        return _business_update(command)

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


def _business_update(message):
    from services.business_events import runtime
    from services.integrations.business_source import load_business_context

    message = " ".join(message.split())
    if not 1 <= len(message) <= 1800 or "[ashbel-event:" in message.lower():
        return _error("כתוב עדכון עסקי באורך של עד 1,800 תווים.", 400)

    source = os.getenv("ASHBEL_CRM_WRITEBACK_SOURCE", "").strip()
    if not (runtime.enabled() and source and os.getenv("ASHBEL_CRM_WRITEBACK_ENABLED", "").lower() == "true"):
        return _error("מסלול עדכוני העסק אינו זמין כרגע.", 503)

    context = load_business_context()
    if context.get("health") != "read_ok" or not context.get("snapshot_sha256"):
        return _error("לא ניתן לקרוא את ה־CRM כרגע. העדכון טרם נקלט.", 503)

    # Match whole words from CRM titles and explicit title segments. A match
    # to more than one open record must stay with the owner for clarification.
    normalized = " " + " ".join(re.findall(r"\w+", message.casefold().replace("_", " "))) + " "
    matches = []
    name_matches = []
    for item in context["actions"]:
        if item["kind"] not in {"customer", "supplier"} or item["disposition"] == "completed":
            continue
        subject = item["subject"]
        names = [subject, *re.split(r"[|—–·]", subject)]
        aliases = {" ".join(re.findall(r"\w+", name.casefold().replace("_", " "))) for name in names}
        if any(len(alias) >= 4 and f" {alias} " in normalized for alias in aliases):
            matches.append(item)
        elif item["kind"] == "customer" and len(names) > 1:
            words = re.findall(r"\w+", names[1].casefold())
            if len(words) > 1 and len(words[-1]) >= 3 and f" {words[-1]} " in normalized:
                name_matches.append(item)
    matches = matches or name_matches
    if len(matches) != 1:
        return _error("כדי לשייך את ההודעה, כתוב בתחילתה את שם הפרויקט או נושא הספק כפי שמופיע בתור העבודה ב־CRM.", 422)

    item = matches[0]
    now = runtime.now()
    day = now.astimezone(ZoneInfo("Asia/Jerusalem")).date().isoformat()
    digest = hashlib.sha256(f"{day}\n{item['subject']}\n{message}".encode()).hexdigest()
    envelope = {
        "source": source,
        "source_event_id": f"console-update-{digest}",
        "source_ref": "ashbelos:owner-console",
        "event_type": "supplier.updated" if item["kind"] == "supplier" else "customer.updated",
        "occurred_at": now.isoformat(),
        "facts": {"work_item_subject": item["subject"], "owner_update": message,
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
