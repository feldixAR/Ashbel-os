"""Read-only, bounded Google Sheets context. No CRM import or outbound effects.

Credentials are read from the environment at call time; the connection is opt-in.
Sheet cells are evidence, never executable instructions. Missing/ambiguous evidence
does not become permission, delivery confirmation, collected revenue or commission.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import re
from urllib.parse import quote

SCOPE = "https://www.googleapis.com/auth/spreadsheets.readonly"
LEAD_HEADERS = ("שם הלקוח", "מזהה ליד", "סטטוס", "פעולה הבאה", "סיכום ומעקב")
WORK_HEADERS = ("נושא / לקוח", "פעולה נדרשת", "מועד", "סטטוס מאומת",
                "אחראי", "הקשר ומידע חשוב", "מקור", "קבוצה אחראית")
LEADS_RANGE = "'לידים'!A1:AE1000"
WORK_RANGE = "'תור עבודה'!A1:H50"
WORK_SECTION_END = "מעקבי לידים"


def enabled() -> bool:
    return os.getenv("ASHBEL_SOURCE_CONTEXT_ENABLED", "").lower() == "true"


def _now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def _read_values(spreadsheet_id: str) -> dict:
    """Only values.batchGet, fixed ranges, readonly OAuth scope and bounded IO."""
    from google.oauth2.service_account import Credentials
    from google.auth.transport.requests import Request
    import requests

    raw = os.environ["ASHBEL_SHEETS_SERVICE_ACCOUNT_JSON"]
    info = json.loads(raw)
    # Do not trust credential-supplied endpoints or use domain-wide delegation.
    if info.get("type") != "service_account" or info.get("token_uri") != "https://oauth2.googleapis.com/token":
        raise ValueError("invalid_credentials")
    credentials = Credentials.from_service_account_info(info, scopes=[SCOPE])
    auth_request = Request(session=requests.Session())
    credentials.refresh(lambda **kwargs: auth_request(**{**kwargs, "timeout": 15}))
    url = f"https://sheets.googleapis.com/v4/spreadsheets/{quote(spreadsheet_id, safe='')}/values:batchGet"
    with requests.get(url, headers={"Authorization": f"Bearer {credentials.token}"},
                      params=[("ranges", LEADS_RANGE), ("ranges", WORK_RANGE),
                              ("valueRenderOption", "FORMATTED_VALUE")],
                      timeout=(5, 15), stream=True, allow_redirects=False) as response:
        response.raise_for_status()
        chunks, size = [], 0
        for chunk in response.iter_content(65536):
            size += len(chunk)
            if size > 4_000_000:
                raise ValueError("response_too_large")
            chunks.append(chunk)
        return json.loads(b"".join(chunks))


def _records(values: list, required: tuple, max_rows: int, max_cols: int,
             section_end: str = "") -> list:
    if not values or len(values) > max_rows or any(len(row) > max_cols for row in values):
        raise ValueError("invalid_shape")
    headers = [str(value).strip() for value in values[0]]
    if len(headers) != len(set(headers)) or not set(required).issubset(headers):
        raise ValueError("schema_mismatch")
    records = []
    for row_num, row in enumerate(values[1:], 2):
        if section_end and row and str(row[0]).startswith(section_end):
            break
        if not any(str(value).strip() for value in row):
            continue
        record = {key: str(row[i]).strip() if i < len(row) else ""
                  for i, key in enumerate(headers)}
        record["_row"] = row_num
        records.append(record)
    else:
        if section_end:
            # Refuse a possibly truncated queue rather than ingest its dynamic section.
            raise ValueError("work_section_boundary_missing")
    return records


def interpret_snapshot(payload: dict, spreadsheet_id: str, fetched_at: str) -> dict:
    ranges = payload.get("valueRanges", [])
    if len(ranges) != 2:
        raise ValueError("missing_ranges")
    lead_values = ranges[0].get("values", [])
    if len(lead_values) == 1000 and any(str(v).strip() for v in lead_values[-1]):
        raise ValueError("lead_range_exhausted")
    leads = _records(lead_values, LEAD_HEADERS, 1000, 31)
    work = _records(ranges[1].get("values", []), WORK_HEADERS, 50, 8, WORK_SECTION_END)
    ids = [row["מזהה ליד"] for row in leads if row["מזהה ליד"]]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate_lead_ids")
    fingerprint = hashlib.sha256(json.dumps(ranges, ensure_ascii=False,
                                          sort_keys=True).encode()).hexdigest()
    decisions, actions = [], []
    capacity_blocked = False
    capacity_confirmed = False
    for row in work:
        status = row["סטטוס מאומת"]
        if status in {"הושלם", "סגור", "בוטל"}:
            continue
        text = " ".join(row[key] for key in WORK_HEADERS[:6])
        evidence = {"range": f"'תור עבודה'!A{row['_row']}:H{row['_row']}",
                    "source_reference": row["מקור"], "snapshot_sha256": fingerprint}
        if status in {"ספק כשיר", "קיבולת מאומתת", "קיבולת ספק מאומתת"}:
            capacity_confirmed = True
        if re.search(r"ספק.{0,25}(חסום|לא זמין)|אין יכולת תמחור|לא להעביר.{0,35}(הצעות|תמחור)|תלות בספק יחיד", text):
            capacity_blocked = True
            decisions.append({"code": "supplier_capacity_blocked", "subject": row["נושא / לקוח"],
                              "instruction": "להכשיר קיבולת ספק לפני הרחבת לידים.", "evidence": evidence})
        if re.search(r"אולם|בחירת מפרט|בחירת מערכות", text) and status not in {"ביקור הושלם", "מפרט אושר", "מערכות אושרו"}:
            decisions.append({"code": "specification_pending", "subject": row["נושא / לקוח"],
                              "instruction": "להמתין לבחירת מפרט מאומתת לפני תמחור מתקדם.", "evidence": evidence})
        if status not in {"הושלם", "סגור", "בוטל"}:
            actions.append({"subject": row["נושא / לקוח"], "action": row["פעולה נדרשת"],
                            "due": row["מועד"], "owner": row["אחראי"], "status": status,
                            "evidence": evidence})
    # Read-only facts retain source wording. Neither a proposal amount nor draft
    # approval proves a sent message, accepted contract, collection or commission.
    proposal_rows = [row for row in leads if row.get("מצב הצעת מחיר", "").strip()
                     not in {"", "טרם הוכנה", "טרם תומחר", "טרם תומחרה", "לא הוכנה"}]
    lead_facts = [{"lead_id": row["מזהה ליד"], "subject": row["שם הלקוח"],
                   "status": row["סטטוס"], "next_action": row["פעולה הבאה"],
                   "proposal_status": row.get("מצב הצעת מחיר", ""),
                   "delivery": "not_verified", "commission": "not_verified",
                   "evidence": {"range": f"'לידים'!A{row['_row']}:AE{row['_row']}",
                                "snapshot_sha256": fingerprint}}
                  for row in proposal_rows[:25]]
    capacity_state = "blocked" if capacity_blocked else "confirmed" if capacity_confirmed else "unknown"
    if capacity_state == "unknown":
        decisions.append({"code": "supplier_capacity_unknown", "subject": "קיבולת ספקים",
                          "instruction": "לאמת קיבולת ספק לפני הרחבת לידים; היעדר חסימה אינו כשירות.",
                          "evidence": {"range": WORK_RANGE, "snapshot_sha256": fingerprint}})
    # Preserve every task, but do not promote a conflicting action for execution.
    for action in actions:
        action["blocked_reasons"] = []
        if capacity_state != "confirmed" and re.search(r"(הרחב|הרחבת|גיוס|איתור|רכישת).{0,15}לידים|lead acquisition", action["action"], re.I):
            action["blocked_reasons"].append(f"supplier_capacity_{capacity_state}")
        if any(d["code"] == "specification_pending" and d["subject"] == action["subject"] for d in decisions) and re.search(r"תמחור|לתמחר", action["action"]):
            action["blocked_reasons"].append("specification_pending")
    return {"health": "read_ok", "fetched_at": fetched_at, "source_updated_at": None,
            "source_freshness": "not_verified", "spreadsheet_id": spreadsheet_id,
            "snapshot_sha256": fingerprint, "lead_count": len(leads), "work_count": len(work),
            "proposal_lead_facts": lead_facts, "proposal_lead_facts_limit": 25,
            "proposal_lead_facts_total": len(proposal_rows),
            "proposal_lead_facts_truncated": max(0, len(proposal_rows) - len(lead_facts)),
            "capacity_state": capacity_state,
            "lead_acquisition_allowed": capacity_state == "confirmed", "decisions": decisions,
            "actions": actions, "source_ranges": [LEADS_RANGE, WORK_RANGE],
            "financial_truth": {"collected_commission_ils": None,
                                "recognition": "requires_collection_evidence"},
            "delivery_truth": "approved_draft_is_not_sent",
            "permissions": "read_only_no_external_actions",
            "coverage": "bounded_sheet_snapshot_not_all_project_history"}


def load_business_context() -> dict:
    if not enabled():
        return {"health": "disabled", "source_freshness": "not_verified"}
    spreadsheet_id = os.getenv("ASHBEL_SOURCE_SPREADSHEET_ID", "").strip()
    if not re.fullmatch(r"[A-Za-z0-9_-]{20,150}", spreadsheet_id) or not os.getenv("ASHBEL_SHEETS_SERVICE_ACCOUNT_JSON"):
        return {"health": "not_configured", "source_freshness": "not_verified",
                "lead_acquisition_allowed": False, "actions": []}
    try:
        return interpret_snapshot(_read_values(spreadsheet_id), spreadsheet_id, _now())
    except Exception:
        # Never log provider bodies, credential JSON, tokens or exception strings.
        return {"health": "unavailable", "checked_at": _now(),
                "source_freshness": "not_verified", "lead_acquisition_allowed": False,
                "actions": [], "error_code": "source_read_or_validation_failed"}


def context_plan(context: dict) -> dict:
    """Safe daily-planning projection; not an execution or approval command."""
    if context.get("health") != "read_ok":
        return {"business_context": context,
                "top_action": "מקור האמת אינו זמין או לא מחובר; לאמת קיבולת ומשימות לפני המלצות עסקיות.",
                "priority_items": [], "recommendations_only": True}
    decisions = context["decisions"]
    top = next((d["instruction"] for d in decisions if d["code"] in {"supplier_capacity_blocked", "supplier_capacity_unknown"}),
               "לאמת את המשימות הפתוחות במקור לפני ביצוע.")
    return {"business_context": context, "top_action": top,
            "priority_items": [a for a in context["actions"] if not a["blocked_reasons"]][:10],
            "recommendations_only": True}
