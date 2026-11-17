"""Read-only source pricing -> durable quote events, never procurement approval.

The source workbook remains authoritative. Values are preserved as quote
references; neither an offer, a source price label nor a reconciled row total
becomes a signed customer contract, contractor purchase cost or collection.
"""
from __future__ import annotations

import datetime as dt
from decimal import Decimal, InvalidOperation
import hashlib
import json
import os
import re
from urllib.parse import quote, urlsplit

SCOPE = "https://www.googleapis.com/auth/spreadsheets.readonly"
READ_RANGE = "'מחירי מקור'!A4:T2000"
HEADERS = ("מזהה", "הצעה", "פרויקט", "תאריך מקור", "פרט", "רוחב מ״מ", "גובה מ״מ",
           "ארגז מ״מ", "כמות", "סדרה", "פתיחה", "זיגוג", "תריס", "מחיר יח׳ לפני מע״מ",
           "סכום מקור", "כלול בסיכום 1/0", "סוג מחיר", "עמוד PDF", "הערה", "מקור")


def enabled():
    return os.getenv("ASHBEL_PRICING_SOURCE_ENABLED", "").lower() == "true"


def _sheet_id():
    value = os.getenv("ASHBEL_PRICING_SPREADSHEET_ID", "").strip()
    if not re.fullmatch(r"[A-Za-z0-9_-]{20,150}", value):
        raise ValueError("pricing_spreadsheet_not_configured")
    return value


def _read_values(spreadsheet_id):
    from google.oauth2.service_account import Credentials
    from google.auth.transport.requests import Request
    import requests

    info = json.loads(os.environ["ASHBEL_SHEETS_SERVICE_ACCOUNT_JSON"])
    if (info.get("type") != "service_account" or info.get("token_uri") != "https://oauth2.googleapis.com/token"
            or info.get("subject") or info.get("delegates")
            or info.get("universe_domain", "googleapis.com") != "googleapis.com"):
        raise ValueError("invalid_credentials")
    credentials = Credentials.from_service_account_info(info, scopes=[SCOPE])
    auth_request = Request(session=requests.Session())
    credentials.refresh(lambda **kwargs: auth_request(**{**kwargs, "timeout": 15}))
    url = "https://sheets.googleapis.com/v4/spreadsheets/" + quote(spreadsheet_id, safe="") + "/values/" + quote(READ_RANGE, safe="")
    with requests.get(url, headers={"Authorization": "Bearer " + credentials.token},
                      params={"valueRenderOption": "UNFORMATTED_VALUE"},
                      timeout=(5, 15), allow_redirects=False, stream=True) as response:
        if response.status_code != 200:
            raise ValueError("pricing_source_http_" + str(response.status_code))
        chunks, size = [], 0
        for chunk in response.iter_content(65536):
            size += len(chunk)
            if size > 4_000_000:
                raise ValueError("pricing_response_too_large")
            chunks.append(chunk)
        return json.loads(b"".join(chunks)).get("values", [])


def _text(value):
    return str(value).strip() if value is not None else ""


def _number(value, positive=False, integer=False):
    if isinstance(value, bool) or value is None or value == "":
        return None
    try:
        number = Decimal(str(value))
        if not number.is_finite() or number < 0 or number > Decimal("1000000000"):
            return None
        if positive and number <= 0 or integer and number != int(number):
            return None
        return int(number) if integer else format(number.normalize(), "f")
    except (InvalidOperation, TypeError, ValueError):
        return None


def _public_link(value):
    value = _text(value)
    try:
        parsed = urlsplit(value)
        return value if parsed.scheme == "https" and parsed.hostname and not parsed.username and not parsed.password else None
    except ValueError:
        return None


def interpret_values(values, spreadsheet_id, fetched_at):
    """Build complete bounded envelopes before publishing any of this snapshot."""
    try:
        stamp = dt.datetime.fromisoformat(fetched_at.replace("Z", "+00:00"))
        if stamp.tzinfo is None:
            raise ValueError()
    except (ValueError, AttributeError):
        raise ValueError("pricing_fetch_time_requires_timezone") from None
    if not isinstance(values, list) or not values or len(values) >= 1997:
        raise ValueError("pricing_source_missing_or_truncated")
    if not isinstance(values[0], list) or tuple(map(_text, values[0])) != HEADERS:
        raise ValueError("pricing_schema_mismatch")
    grouped, seen = {}, set()
    for row_number, source in enumerate(values[1:], 5):
        if not isinstance(source, list) or len(source) > 20:
            raise ValueError("pricing_row_shape")
        if not any(_text(value) for value in source):
            continue
        row = source + [""] * (20 - len(source))
        if any(len(_text(value)) > 3000 for value in row):
            raise ValueError("pricing_cell_too_large")
        line_id, quote_id, project = map(_text, row[:3])
        if not line_id or not quote_id or not project or len(quote_id) > 100 or len(project) > 300:
            raise ValueError("pricing_identity_missing")
        if line_id in seen:
            raise ValueError("pricing_duplicate_line_identity")
        seen.add(line_id)
        group = grouped.setdefault(quote_id, {"project": project, "rows": []})
        if group["project"] != project:
            raise ValueError("pricing_quote_project_conflict")
        if len(group["rows"]) >= 200:
            raise ValueError("pricing_quote_too_many_lines")
        row_ref = f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/edit#range=" + quote(f"'מחירי מקור'!A{row_number}:T{row_number}", safe="")
        included = _number(row[15], integer=True)
        if included not in (0, 1):
            included = None
        numbers = {
            "width_mm": _number(row[5], positive=True), "height_mm": _number(row[6], positive=True),
            "shutter_box_mm": _number(row[7]), "quantity": _number(row[8], positive=True, integer=True),
            "unit_price_ex_vat_ils": _number(row[13]), "source_line_total_ex_vat_ils": _number(row[14]),
        }
        missing = [key for key, value in numbers.items() if value is None]
        pdf = _public_link(row[19])
        if not pdf:
            missing.append("source_document_link")
        if included is None:
            missing.append("included_in_summary")
        group["rows"].append({
            "line_id": line_id, "opening_id": _text(row[4]), **numbers,
            "system": _text(row[9]) or None, "opening_type": _text(row[10]) or None,
            "glass": _text(row[11]) or None, "shutter": _text(row[12]) or None,
            "included_in_summary": included, "is_alternative": included == 0,
            "source_price_type": _text(row[16]) or None, "source_date": _text(row[3]) or None,
            "source_page": _text(row[17]) or None, "notes": _text(row[18]),
            "source_ref": row_ref, "source_document_ref": pdf, "missing": missing,
            "price_kind": "source_sales_quote_reference", "purchase_price_verified": False,
        })
    envelopes = []
    source_ref = f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/edit"
    for quote_id, group in sorted(grouped.items()):
        rows = group["rows"]
        included = [row for row in rows if row["included_in_summary"] == 1]
        alternatives = [row for row in rows if row["included_in_summary"] == 0]
        # Incomplete or unclassified lines never disappear into a zero total.
        total = (sum((Decimal(row["source_line_total_ex_vat_ils"]) for row in included), Decimal(0))
                 if included and all(row["included_in_summary"] is not None for row in rows)
                 and all(row["source_line_total_ex_vat_ils"] is not None for row in included) else None)
        reference = {"quote_id": quote_id, "project_name": group["project"],
                     "price_kind": "source_sales_quote_reference", "source_ref": source_ref,
                     "sum_included_source_lines_ex_vat_ils": str(total) if total is not None else None,
                     "source_row_count": len(rows), "included_line_count": len(included),
                     "alternative_line_count": len(alternatives), "document_grand_total_verified": False}
        facts = {"project_id": "pricing-project:" + group["project"], "project_name": group["project"],
                 "quote_id": quote_id, "pricing_spreadsheet_id": spreadsheet_id,
                 "quote_lines": included, "alternative_quote_lines": alternatives,
                 "unclassified_quote_lines": [row for row in rows if row["included_in_summary"] is None],
                 "historical_sale_quotes": [reference], "purchase_quotes": [], "collections": [],
                 "specification_approval_status": "not_provided_by_pricing_source", "contact_permission": "unverified",
                 "source_rows_are_reference_only": True}
        digest = hashlib.sha256(json.dumps(facts, sort_keys=True, ensure_ascii=False, allow_nan=False).encode()).hexdigest()
        envelope = {"source": "existing_pricing_sheet", "source_event_id": "quote:" + quote_id + ":" + digest,
                    "event_type": "quote.received", "source_ref": source_ref,
                    "occurred_at": stamp.astimezone(dt.timezone.utc).isoformat(), "facts": facts}
        if len(json.dumps(envelope, ensure_ascii=False, allow_nan=False).encode()) > 65536:
            raise ValueError("pricing_quote_event_too_large")
        envelopes.append(envelope)
    return envelopes


def load_pricing_events():
    if not enabled():
        return {"health": "disabled", "events": []}
    if not os.getenv("ASHBEL_SHEETS_SERVICE_ACCOUNT_JSON", "").strip():
        return {"health": "not_configured", "events": []}
    try:
        sheet = _sheet_id()
        stamp = dt.datetime.now(dt.timezone.utc).isoformat()
        events = interpret_values(_read_values(sheet), sheet, stamp)
        return {"health": "read_ok", "events": events, "quote_count": len(events),
                "fetched_at": stamp, "source_range": READ_RANGE}
    except Exception as exc:
        return {"health": "unavailable", "events": [], "error_code": type(exc).__name__}


def enqueue_pricing_events():
    """Retrying this read/publish is safe: source identities are content-stable."""
    loaded = load_pricing_events()
    result = {"health": loaded["health"], "queued": 0, "duplicates": 0, "event_ids": [],
              "source_writeback": "not_attempted", "external_execution": False}
    if loaded["health"] != "read_ok":
        if "error_code" in loaded:
            result["error_code"] = loaded["error_code"]
        return result
    try:
        from services.business_events.runtime import ingest_event
        for envelope in loaded["events"]:
            event = ingest_event(envelope)
            result["event_ids"].append(event["id"])
            result["duplicates" if event["duplicate"] else "queued"] += 1
    except Exception as exc:
        result.update(health="event_storage_unavailable", error_code=type(exc).__name__)
    return result
