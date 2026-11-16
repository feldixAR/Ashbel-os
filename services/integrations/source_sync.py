"""Governed append-only bridge into the existing 44-column CRM.

Preview -> exact hash confirmation -> durable workbook claim -> one append ->
readback. Any ambiguous append or interrupted worker remains uncertain until
read-only reconciliation. An expired claim is never silently replayed.
"""
from __future__ import annotations
import datetime as dt
import hashlib
import ipaddress
import json
import os
import re
from urllib.parse import quote, urlsplit, urlunsplit, parse_qsl, urlencode

from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from services.storage.db import get_session
from services.storage.models.base import new_uuid
from services.storage.models.source_sync import SourceSyncOperation, SourceSyncLease

HEADERS = (
    "עדיפות", "סטטוס", "תאריך פעולה", "שלב בנייה", "חודש", "אזור ויישוב", "מה ביקש",
    "שם הלקוח", "לחיוג", "WhatsApp", "פעולה הבאה", "סיכום ומעקב", "מזהה ליד", "אזור",
    "איש קשר לפי המקור", "טלפון", "דוא״ל", "סוג עבודה שזוהה", "דירוג רלוונטיות",
    "תאריך שיחה אחרונה", "חומר שהתקבל", "חומר שיווקי שנשלח", "מצב הצעת מחיר", "סכום הצעה",
    "קישור לתיקיית לקוח", "הערות / מעקב מקור", "קובץ מקור", "שורת מקור", "קישור למקור",
    "יישוב מקור", "שם לקוח מקור", "סוג ישות", "קטגוריית מקור", "תאריך איתור",
    "סוג פרויקט", "צורך באלומיניום", "איכות הזדמנות", "רמת ביטחון", "הרשאת פנייה",
    "סטטוס אימות מקור", "תאריך פרסום מקור", "מפתח מקור חיצוני", "מצב אירוע/סנכרון", "מזהה אירוע",
)
ENTITY_TYPES = {"לקוח", "ספק", "מתקין", "שותף עסקי"}
READ_RANGE = "'לידים'!A1:AR2000"
APPEND_RANGE = "'לידים'!A:AR"
WRITE_SCOPE = "https://www.googleapis.com/auth/spreadsheets"


def now():
    return dt.datetime.now(dt.timezone.utc)


def tenant():
    return os.getenv("BUSINESS_ID", "ashbel")


def enabled():
    return os.getenv("ASHBEL_SOURCE_SYNC_ENABLED", "").lower() == "true"


def sheet_id():
    value = os.getenv("ASHBEL_SOURCE_SPREADSHEET_ID", "").strip()
    if not re.fullmatch(r"[A-Za-z0-9_-]{20,150}", value):
        raise ValueError("source_spreadsheet_not_configured")
    return value


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     allow_nan=False, separators=(",", ":")).encode()).hexdigest()


def canonical_url(value):
    try:
        parts = urlsplit(value.strip())
        host = (parts.hostname or "").lower().rstrip(".")
        if parts.scheme != "https" or not host or parts.username or parts.password or parts.port not in (None, 443):
            raise ValueError()
        try:
            ipaddress.ip_address(host)
        except ValueError:
            pass
        else:
            raise ValueError()
        if "." not in host or host.endswith((".local", ".internal", ".localhost")) or host == "localhost":
            raise ValueError()
        # The procurement portal publishes both aliases for the same record.
        host = {"www.mr.gov.il": "mr.gov.il"}.get(host, host)
        query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
                 if not k.lower().startswith("utm_") and k.lower() not in {"fbclid", "gclid"}]
        return urlunsplit(("https", host, parts.path.rstrip("/") or "/", urlencode(sorted(query)), ""))
    except (TypeError, ValueError, AttributeError):
        raise ValueError("invalid_public_source_url") from None


def normalized_phone(value):
    digits = re.sub(r"\D", "", value)
    if digits.startswith("00972"):
        digits = digits[2:]
    if digits.startswith("0"):
        digits = "972" + digits[1:]
    return digits if 8 <= len(digits) <= 15 else ""


def identity(value):
    return re.sub(r"[\W_]+", "", value.casefold(), flags=re.UNICODE)


def candidate_fields(raw):
    if not isinstance(raw, dict) or len(json.dumps(raw, ensure_ascii=False, allow_nan=False).encode()) > 16000:
        raise ValueError("invalid_candidate")
    required = ("source_key", "source_url", "name", "city", "project_type", "project_stage",
                "aluminum_need", "next_action", "found_at", "published_at", "quality", "confidence")
    result = {}
    for key in required:
        value = raw.get(key)
        if not isinstance(value, str) or not value.strip() or len(value) > (2000 if key == "source_url" else 1000):
            raise ValueError("invalid_" + key)
        result[key] = value.strip()
    for key in ("phone", "email", "details"):
        value = raw.get(key, "")
        if not isinstance(value, str) or len(value) > 3000:
            raise ValueError("invalid_" + key)
        result[key] = value.strip()
    result["source_url"] = canonical_url(result["source_url"])
    result["entity_type"] = raw.get("entity_type", "לקוח")
    if result["entity_type"] not in ENTITY_TYPES:
        raise ValueError("invalid_entity_type")
    for key in ("found_at", "published_at"):
        try:
            dt.date.fromisoformat(result[key])
        except ValueError:
            raise ValueError("invalid_" + key) from None
    # Published contact information never grants outreach permission.
    result["contact_permission"] = "unverified"
    return result


def validate_candidate(raw):
    from services.storage.models.task import TaskModel
    candidate = candidate_fields(raw)
    verification_id = raw.get("verification_id", "")
    if not isinstance(verification_id, str) or not verification_id:
        raise ValueError("source_verification_required")
    with get_session() as session:
        task = session.query(TaskModel).filter_by(id=verification_id, type="public_source_review",
                                                 status="done").one_or_none()
        if not task or (task.input_data or {}).get("business_id") != tenant():
            raise ValueError("source_verification_required")
        verification = task.output_data or {}
        if (verification.get("source_url") != candidate["source_url"]
                or verification.get("candidate_hash") != digest(candidate)
                or verification.get("reviewer") != "authenticated_owner"):
            raise ValueError("source_verification_mismatch")
        checked_at = dt.datetime.fromisoformat(verification["checked_at"])
        if checked_at < now() - dt.timedelta(hours=24):
            raise ValueError("source_verification_expired")
        candidate["verification"] = {**verification, "verification_id": verification_id}
    return candidate


def snapshot(values):
    if not isinstance(values, list) or not values or len(values) >= 2000:
        raise ValueError("source_range_exhausted_or_missing")
    headers = tuple(str(x).strip() for x in values[0])
    if headers != HEADERS or any(not isinstance(row, list) or len(row) > 44 for row in values):
        raise ValueError("source_schema_mismatch")
    # Preserve blank row positions so duplicate evidence points to the real CRM row.
    rows = [list(map(str, row)) + [""] * (44 - len(row)) for row in values[1:]]
    ids = [r[12] for r in rows if r[12]]
    if len(ids) != len(set(ids)):
        raise ValueError("existing_duplicate_lead_ids")
    return rows, digest(values)


def duplicate(candidate, rows):
    url = candidate["source_url"]
    phone = normalized_phone(candidate["phone"])
    source_key = identity(candidate["source_key"])
    anchored_name = (identity(candidate["name"]), identity(candidate["city"]))
    expected_id = lead_id(candidate)
    for index, row in enumerate(rows, 2):
        reasons = []
        if row[12] == expected_id:
            reasons.append("lead_id")
        if row[41] and identity(row[41]) == source_key:
            reasons.append("external_source_key")
        if row[28]:
            try:
                if canonical_url(row[28]) == url:
                    reasons.append("source_url")
            except ValueError:
                pass
        if phone and any(normalized_phone(row[p]) == phone for p in (8, 15) if row[p]):
            reasons.append("phone")
        if all(anchored_name) and any(
            (identity(row[n]), identity(row[c])) == anchored_name
            for n, c in ((7, 5), (30, 29))
        ):
            reasons.append("anchored_name_city")
        if reasons:
            return {"row_hint": index, "lead_id": row[12], "reasons": reasons}
    return None


def lead_id(candidate):
    key = re.sub(r"[^A-Za-z0-9_-]", "", candidate["source_key"])
    return "EXT-" + (key[:100] if key else digest(candidate["source_url"])[:24])


def crm_row(candidate):
    fields = {
        "עדיפות": "3", "סטטוס": "הזדמנות חיצונית מאומתת — אין הרשאת פנייה",
        "תאריך פעולה": (dt.date.fromisoformat(candidate["found_at"]) - dt.date(1899, 12, 30)).days, "שלב בנייה": candidate["project_stage"],
        "אזור ויישוב": candidate["city"], "מה ביקש": candidate["aluminum_need"],
        "שם הלקוח": candidate["name"], "פעולה הבאה": candidate["next_action"],
        "סיכום ומעקב": candidate["details"], "מזהה ליד": lead_id(candidate),
        "איש קשר לפי המקור": candidate["name"], "טלפון": candidate["phone"],
        "דוא״ל": candidate["email"], "סוג עבודה שזוהה": candidate["project_type"],
        "דירוג רלוונטיות": candidate["quality"], "הערות / מעקב מקור": "מקור פומבי; פרטי קשר אינם הרשאת פנייה",
        "קישור למקור": candidate["source_url"], "יישוב מקור": candidate["city"],
        "שם לקוח מקור": candidate["name"], "סוג ישות": candidate["entity_type"],
        "קטגוריית מקור": "חיצוני", "תאריך איתור": candidate["found_at"],
        "סוג פרויקט": candidate["project_type"], "צורך באלומיניום": candidate["aluminum_need"],
        "איכות הזדמנות": candidate["quality"], "רמת ביטחון": candidate["confidence"],
        "הרשאת פנייה": "לא אומתה — אין פנייה אוטומטית",
        "סטטוס אימות מקור": "אומת בבדיקת מקור; כשירות עסקית טעונה בדיקה",
        "תאריך פרסום מקור": candidate["published_at"], "מפתח מקור חיצוני": candidate["source_key"],
        "מצב אירוע/סנכרון": "נשמר במקור — ממתין לעיבוד",
        "מזהה אירוע": "discovery:" + candidate["source_key"],
    }
    return [fields.get(header, "") for header in HEADERS]


class SheetsClient:
    """Fixed Sheets endpoints, dedicated environment credential, no redirects."""
    def __init__(self):
        from google.oauth2.service_account import Credentials
        from google.auth.transport.requests import Request
        import requests
        raw = os.getenv("ASHBEL_SHEETS_WRITER_SERVICE_ACCOUNT_JSON", "")
        if not raw:
            raise ValueError("source_writer_not_configured")
        info = json.loads(raw)
        if info.get("type") != "service_account" or info.get("token_uri") != "https://oauth2.googleapis.com/token":
            raise ValueError("invalid_writer_credentials")
        credentials = Credentials.from_service_account_info(info, scopes=[WRITE_SCOPE])
        request = Request(session=requests.Session())
        credentials.refresh(lambda **kwargs: request(**{**kwargs, "timeout": 15}))
        self.session = requests.Session()
        self.session.headers["Authorization"] = "Bearer " + credentials.token
        self.base = "https://sheets.googleapis.com/v4/spreadsheets/" + quote(sheet_id(), safe="") + "/values/"

    def _call(self, method, path, action="", **kwargs):
        with self.session.request(method, self.base + quote(path, safe="") + action, timeout=(5, 20),
                                  allow_redirects=False, stream=True, **kwargs) as response:
            response.raise_for_status()
            data, size = [], 0
            for chunk in response.iter_content(65536):
                size += len(chunk)
                if size > 4_000_000:
                    raise ValueError("response_too_large")
                data.append(chunk)
            return json.loads(b"".join(data))

    def read(self):
        return self._call("GET", READ_RANGE, params={"valueRenderOption": "UNFORMATTED_VALUE"}).get("values", [])

    def append(self, row):
        # The only write operation in this module. RAW forbids formula evaluation.
        return self._call("POST", APPEND_RANGE, action=":append",
                          params={"valueInputOption": "RAW", "insertDataOption": "INSERT_ROWS",
                                  "includeValuesInResponse": "true"},
                          json={"majorDimension": "ROWS", "values": [row]})

    def read_row(self, number):
        return self._call("GET", "'לידים'!A%d:AR%d" % (number, number),
                          params={"valueRenderOption": "UNFORMATTED_VALUE"}).get("values", [])


def _client():
    return SheetsClient()



class SourcePreviewClient:
    """A preview can read through the existing Viewer credential, never write."""
    def read(self):
        from services.integrations.business_source import _read_values
        ranges = _read_values(sheet_id()).get("valueRanges", [])
        if not ranges:
            raise ValueError("source_unavailable")
        return ranges[0].get("values", [])


def _preview_client():
    if os.getenv("ASHBEL_SHEETS_SERVICE_ACCOUNT_JSON", ""):
        return SourcePreviewClient()
    return _client()

def _require_enabled():
    if not enabled():
        raise ValueError("source_sync_disabled")


def prepare_append(raw, client=None):
    _require_enabled()
    candidate = validate_candidate(raw)
    client = client or _preview_client()
    rows, snapshot_hash = snapshot(client.read())
    match = duplicate(candidate, rows)
    if match:
        return {"status": "duplicate", "duplicate": match, "appended": False}
    expected = crm_row(candidate)
    preview_hash = digest({"business_id": tenant(), "spreadsheet_id": sheet_id(),
                           "candidate": candidate, "row": expected, "snapshot_hash": snapshot_hash})
    operation = SourceSyncOperation(id=new_uuid(), business_id=tenant(), spreadsheet_id=sheet_id(),
                                    preview_hash=preview_hash, snapshot_hash=snapshot_hash,
                                    candidate=candidate, expected_row=expected, status="prepared",
                                    expires_at=(now() + dt.timedelta(minutes=30)).isoformat())
    try:
        with get_session() as session:
            session.add(operation)
            session.flush()
    except IntegrityError:
        with get_session() as session:
            operation = session.query(SourceSyncOperation).filter_by(
                business_id=tenant(), preview_hash=preview_hash).one()
            # Before-write failures and unused expired previews are safe to
            # prepare again. Ambiguous/in-flight writes are never reset here.
            if operation.status in {"read_failed", "stale_preview"} or (
                    operation.status == "prepared" and operation.expires_at < now().isoformat()):
                changed = session.execute(update(SourceSyncOperation).where(
                    SourceSyncOperation.id == operation.id,
                    SourceSyncOperation.status == operation.status,
                ).values(status="prepared", claim_token=None, error_code=None,
                         expires_at=(now() + dt.timedelta(minutes=30)).isoformat())).rowcount
                session.expire(operation)
                session.refresh(operation)
    return {"operation_id": operation.id, "status": operation.status, "preview_hash": preview_hash,
            "expires_at": operation.expires_at, "recipient_outreach_permission": "unverified",
            "row": expected, "appended": False}


def _operation(operation_id):
    with get_session() as session:
        row = session.query(SourceSyncOperation).filter_by(id=operation_id, business_id=tenant(),
                                                         spreadsheet_id=sheet_id()).one_or_none()
        if not row:
            raise ValueError("source_operation_not_found")
        return row


def _claim(operation):
    token = new_uuid()
    try:
        with get_session() as session:
            session.add(SourceSyncLease(business_id=tenant(), spreadsheet_id=sheet_id()))
            session.flush()
    except IntegrityError:
        pass
    with get_session() as session:
        changed = session.execute(update(SourceSyncLease).where(
            SourceSyncLease.business_id == tenant(), SourceSyncLease.spreadsheet_id == sheet_id(),
            SourceSyncLease.token.is_(None),
        ).values(operation_id=operation.id, token=token,
                 expires_at=(now() + dt.timedelta(minutes=5)).isoformat())).rowcount
        if changed != 1:
            return None
        changed = session.execute(update(SourceSyncOperation).where(
            SourceSyncOperation.id == operation.id, SourceSyncOperation.business_id == tenant(),
            SourceSyncOperation.status == "prepared",
        ).values(status="in_flight", claim_token=token)).rowcount
        if changed != 1:
            session.rollback()
            return None
    return token


def _finish(operation_id, token, status, result=None, release=True, error_code=None):
    with get_session() as session:
        lease = session.get(SourceSyncLease, (tenant(), sheet_id()))
        if not lease or lease.token != token or lease.operation_id != operation_id:
            return False
        changed = session.execute(update(SourceSyncOperation).where(
            SourceSyncOperation.id == operation_id, SourceSyncOperation.business_id == tenant(),
            SourceSyncOperation.claim_token == token, SourceSyncOperation.status.in_(["in_flight", "uncertain"]),
        ).values(status=status, result=result, error_code=error_code)).rowcount
        if changed == 1 and release:
            lease.token = None
            lease.operation_id = None
            lease.expires_at = None
        return changed == 1


def _row_equal(actual, expected):
    return bool(actual) and (list(map(str, actual)) + [""] * (44 - len(actual))) == list(map(str, expected))


def commit_append(operation_id, preview_hash, client=None):
    _require_enabled()
    operation = _operation(operation_id)
    if not isinstance(preview_hash, str) or preview_hash != operation.preview_hash:
        raise ValueError("preview_hash_mismatch")
    if operation.status != "prepared":
        result = _ensure_business_event(operation, operation.result) if operation.status == "committed" else operation.result
        return {"status": operation.status, "appended": operation.status == "committed",
                "result": result}
    if operation.expires_at < now().isoformat():
        raise ValueError("preview_expired")
    # Credential/token failures occur before claiming and before any write.
    client = client or _client()
    token = _claim(operation)
    if not token:
        return {"status": "busy_or_already_claimed", "appended": False}
    try:
        current_values = client.read()
        rows, current_hash = snapshot(current_values)
        minimum_new_row = len(current_values) + 1
        match = duplicate(operation.candidate, rows)
        if match:
            _finish(operation_id, token, "duplicate", result=match)
            return {"status": "duplicate", "appended": False, "duplicate": match}
        if current_hash != operation.snapshot_hash:
            _finish(operation_id, token, "stale_preview", error_code="source_changed")
            return {"status": "stale_preview", "appended": False}
    except Exception as exc:
        # No write has been attempted, so this operation can safely be prepared again.
        _finish(operation_id, token, "read_failed", error_code=type(exc).__name__)
        return {"status": "read_failed", "appended": False, "error_code": type(exc).__name__}
    try:
        response = client.append(operation.expected_row)  # exactly one network attempt
        updated_range = response.get("updates", {}).get("updatedRange", "")
        match = re.fullmatch(r"(?:'לידים'|לידים)!A(\d+):AR\1", updated_range)
        if not match:
            raise ValueError("append_range_not_verified")
        number = int(match.group(1))
        if number < minimum_new_row:
            raise ValueError("append_not_after_existing_rows")
        actual = client.read_row(number)
        if len(actual) != 1 or not _row_equal(actual[0], operation.expected_row):
            raise ValueError("append_readback_mismatch")
        result = {"spreadsheet_id": sheet_id(), "range": updated_range, "row": number,
                  "lead_id": lead_id(operation.candidate),
                  "source_url": operation.candidate["source_url"], "provider_response": response}
        if not _finish(operation_id, token, "committed", result=result):
            return {"status": "uncertain", "appended": False, "requires_reconciliation": True}
        return {"status": "committed", "appended": True, "result": _ensure_business_event(operation, result)}
    except Exception as exc:
        _finish(operation_id, token, "uncertain", release=False, error_code=type(exc).__name__)
        return {"status": "uncertain", "appended": False, "requires_reconciliation": True,
                "error_code": type(exc).__name__}


def reconcile(operation_id, client=None):
    """Read-only recovery. Missing/ambiguous evidence never releases a claim."""
    _require_enabled()
    operation = _operation(operation_id)
    if operation.status not in {"uncertain", "in_flight"}:
        return {"status": operation.status, "result": operation.result}
    with get_session() as session:
        lease = session.get(SourceSyncLease, (tenant(), sheet_id()))
        if not lease or lease.operation_id != operation_id:
            raise ValueError("operation_lease_missing")
        token, expiry = lease.token, lease.expires_at
    if operation.status == "in_flight" and expiry and expiry > now().isoformat():
        return {"status": "in_flight", "requires_reconciliation": True}
    client = client or _client()
    values = client.read()
    snapshot(values)
    matches = [number for number, row in enumerate(values[1:], 2)
               if len(row) > 12 and str(row[12]) == lead_id(operation.candidate)]
    if len(matches) == 1:
        number = matches[0]
        actual = client.read_row(number)
        if len(actual) == 1 and _row_equal(actual[0], operation.expected_row):
            result = {"spreadsheet_id": sheet_id(), "row": number,
                      "range": "'לידים'!A%d:AR%d" % (number, number),
                      "lead_id": lead_id(operation.candidate), "reconciled": True}
            if _finish(operation_id, token, "committed", result=result):
                return {"status": "committed", "appended": True, "result": result}
    _finish(operation_id, token, "uncertain", release=False, error_code="reconciliation_inconclusive")
    return {"status": "uncertain", "appended": False, "requires_operator_review": True}


def recent_operations():
    with get_session() as session:
        rows = session.query(SourceSyncOperation).filter_by(business_id=tenant(), spreadsheet_id=sheet_id()).order_by(
            SourceSyncOperation.created_at.desc()).limit(30).all()
        return [{"id": row.id, "status": row.status, "preview_hash": row.preview_hash,
                 "result": row.result, "error_code": row.error_code} for row in rows]


def _ensure_business_event(operation, result):
    """Event publication can retry independently; a committed append never does."""
    result = dict(result or {})
    if result.get("business_event_id"):
        return result
    candidate = operation.candidate
    try:
        from services.business_events.runtime import ingest_event
        event = ingest_event({
            "source": "verified_public_source",
            "source_event_id": "crm:" + lead_id(candidate),
            "event_type": "opportunity.discovered",
            "source_ref": candidate["source_url"],
            "occurred_at": candidate["verification"]["checked_at"],
            "facts": {
                "crm_record_id": lead_id(candidate), "crm_row": result["row"],
                "name": candidate["name"],
                "entity_type": candidate["entity_type"], "project_type": candidate["project_type"],
                "project_stage": candidate["project_stage"], "aluminum_need": candidate["aluminum_need"],
                "contact_permission": "unverified",
                "source_verification_id": candidate["verification"]["verification_id"],
                "source_published_date": candidate["published_at"],
            },
        })
        result.update(business_event_id=event["id"], business_event_status=event["status"])
        with get_session() as session:
            row = session.get(SourceSyncOperation, operation.id)
            if row and row.business_id == tenant() and row.status == "committed":
                row.result = result
    except Exception as exc:
        result.update(business_event_status="pending_retry", event_error_code=type(exc).__name__)
    return result
