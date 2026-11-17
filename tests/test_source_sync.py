"""Append/reconcile contract tests with synthetic CRM values; no provider secrets."""
import copy
import datetime as dt
import hashlib
import json
import os
from unittest.mock import patch
import pytest

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("ENVIRONMENT", "test")
from services.storage.db import create_all_tables, get_session
from services.storage.models.task import TaskModel
from services.storage.models.source_sync import SourceSyncOperation, SourceSyncLease
from services.integrations import source_sync as sync
from services.integrations import source_discovery as discovery

SHEET = "synthetic-existing-workbook-000000"


@pytest.fixture(autouse=True)
def setup(monkeypatch):
    monkeypatch.setenv("ASHBEL_SOURCE_SYNC_ENABLED", "true")
    monkeypatch.setenv("ASHBEL_SOURCE_DISCOVERY_ENABLED", "true")
    monkeypatch.setenv("ASHBEL_SOURCE_SPREADSHEET_ID", SHEET)
    monkeypatch.setenv("BUSINESS_ID", "synthetic-sync")
    monkeypatch.setenv("ASHBEL_PUBLIC_SOURCE_FEEDS_JSON", json.dumps([{
        "name": "synthetic feed", "url": "https://example.com/feed", "confirmed_public": True,
        "terms_reviewed": True, "allowed_link_hosts": ["example.com"]}]))
    create_all_tables()
    with get_session() as session:
        session.query(SourceSyncOperation).delete()
        session.query(SourceSyncLease).delete()
        session.query(TaskModel).filter(TaskModel.type.in_(["public_source_review", discovery.TYPE])).delete()


def facts(key="SYNTHETIC-1"):
    return dict(source_key=key, source_url="https://example.com/public/" + key,
                name="Synthetic project " + key, city="Synthetic city", project_type="Aluminum windows",
                project_stage="not verified", aluminum_need="Published aluminum requirement",
                next_action="Review qualification only", found_at="2026-11-17", published_at="2026-11-16",
                quality="unqualified", confidence="primary source exists", phone="", email="", details="")


def reviewed(key="SYNTHETIC-1"):
    candidate = facts(key)
    proof = hashlib.sha256(key.encode()).hexdigest()
    with get_session() as session:
        session.add(TaskModel(id=key, type="public_source_review", action="verify_primary_source",
                              status="done", input_data={"business_id": sync.tenant()},
                              output_data={"source_url": candidate["source_url"],
                                           "candidate_hash": sync.digest(sync.candidate_fields(candidate)),
                                           "content_sha256": proof, "reviewer": "authenticated_owner",
                                           "checked_at": sync.now().isoformat()}))
    candidate["verification_id"] = key
    return candidate


class Sheet:
    def __init__(self, rows=None):
        self.values = [list(sync.HEADERS)] + (rows or [])
        self.appends = 0
        self.timeout_after = False
        self.timeout_before = False
        self.bad_readback = False
        self.bad_range = False

    def read(self):
        return copy.deepcopy(self.values)

    def append(self, row):
        self.appends += 1
        if self.timeout_before:
            raise TimeoutError("private credential must not leak")
        self.values.append(list(row))
        if self.timeout_after:
            raise TimeoutError("private credential must not leak")
        number = len(self.values)
        return {"updates": {"updatedRange": ("wrong!A2:AR2" if self.bad_range else
                                             "'לידים'!A%d:AR%d" % (number, number))}}

    def read_row(self, number):
        return [["mismatch"]] if self.bad_readback else copy.deepcopy(self.values[number-1:number])


def test_prepare_exact_commit_and_replay_are_append_once_without_existing_edits():
    existing = [""] * 44
    existing[7], existing[12] = "Existing synthetic", "synthetic-existing"
    sheet = Sheet([existing])
    before = copy.deepcopy(sheet.values)
    candidate = reviewed()
    preview = sync.prepare_append(candidate, sheet)
    assert preview["status"] == "prepared" and sheet.appends == 0
    assert sync.prepare_append(candidate, sheet)["operation_id"] == preview["operation_id"]
    with pytest.raises(ValueError, match="hash_mismatch"):
        sync.commit_append(preview["operation_id"], "different", sheet)
    result = sync.commit_append(preview["operation_id"], preview["preview_hash"], sheet)
    assert result["status"] == "committed" and result["result"]["row"] == 3
    assert sheet.values[:len(before)] == before and sheet.appends == 1
    assert sheet.values[-1][38] == "לא אומתה — אין פנייה אוטומטית"
    assert sync.commit_append(preview["operation_id"], preview["preview_hash"], sheet)["status"] == "committed"
    assert sheet.appends == 1


def test_caller_supplied_hash_is_not_source_review():
    candidate = facts()
    candidate["verification"] = {"content_sha256": "a"*64, "reviewer": "owner",
                                 "source_url": candidate["source_url"], "method": "owner_verified"}
    with pytest.raises(ValueError, match="verification_required"):
        sync.prepare_append(candidate, Sheet())


def test_review_is_bound_to_exact_facts_and_tenant(monkeypatch):
    candidate = reviewed()
    candidate["city"] = "Changed without another review"
    with pytest.raises(ValueError, match="verification_mismatch"):
        sync.prepare_append(candidate, Sheet())
    candidate = facts(); candidate["verification_id"] = "SYNTHETIC-1"
    monkeypatch.setenv("BUSINESS_ID", "another-business")
    with pytest.raises(ValueError, match="verification_required"):
        sync.prepare_append(candidate, Sheet())


@pytest.mark.parametrize("field", ["external_key", "phone", "anchored_identity", "source_url", "lead_id"])
def test_dedup_checks_original_crm_identifiers(field):
    candidate = reviewed()
    candidate["phone"] = "052-000-0000"
    # Re-review changed contact facts.
    with get_session() as session:
        session.get(TaskModel, candidate["verification_id"]).output_data = {
            "source_url": candidate["source_url"], "candidate_hash": sync.digest(sync.candidate_fields(candidate)),
            "reviewer": "authenticated_owner", "checked_at": sync.now().isoformat()}
    row = [""]*44; row[12] = "already-existing"
    if field == "external_key": row[41] = candidate["source_key"]
    if field == "phone": row[15] = "+972520000000"
    if field == "anchored_identity": row[7], row[5] = candidate["name"], candidate["city"]
    if field == "source_url": row[28] = candidate["source_url"] + "?utm_source=synthetic#fragment"
    if field == "lead_id": row[12] = sync.lead_id(sync.candidate_fields(candidate))
    sheet = Sheet([row])
    assert sync.prepare_append(candidate, sheet)["status"] == "duplicate"
    assert sheet.appends == 0


def test_mr_portal_alias_dedup_and_raw_formula_safety():
    assert sync.canonical_url("https://www.mr.gov.il/ilgstorefront/he/p/123/?utm_source=x") == \
           sync.canonical_url("https://mr.gov.il/ilgstorefront/he/p/123")
    candidate = reviewed()
    assert sync.crm_row(sync.validate_candidate(candidate))[7].startswith("Synthetic")


def test_source_change_invalidates_preview_without_write():
    sheet = Sheet()
    preview = sync.prepare_append(reviewed(), sheet)
    unrelated = [""]*44; unrelated[12] = "changed-by-another-user"
    sheet.values.append(unrelated)
    result = sync.commit_append(preview["operation_id"], preview["preview_hash"], sheet)
    assert result["status"] == "stale_preview" and sheet.appends == 0


def test_timeout_after_apply_quarantines_claim_and_readonly_reconcile_resolves():
    sheet = Sheet()
    preview = sync.prepare_append(reviewed(), sheet)
    sheet.timeout_after = True
    result = sync.commit_append(preview["operation_id"], preview["preview_hash"], sheet)
    assert result["status"] == "uncertain" and sheet.appends == 1
    assert "private" not in json.dumps(result)
    assert sync.commit_append(preview["operation_id"], preview["preview_hash"], sheet)["status"] == "uncertain"
    another = sync.prepare_append(reviewed("SYNTHETIC-2"), sheet)
    assert sync.commit_append(another["operation_id"], another["preview_hash"], sheet)["status"] == "busy_or_already_claimed"
    assert sync.reconcile(preview["operation_id"], sheet)["status"] == "committed"
    assert sheet.appends == 1
    sheet.timeout_after = False
    assert sync.commit_append(another["operation_id"], another["preview_hash"], sheet)["status"] == "committed"
    assert sheet.appends == 2


def test_timeout_before_apply_is_not_assumed_safe_to_retry():
    sheet = Sheet()
    preview = sync.prepare_append(reviewed(), sheet)
    sheet.timeout_before = True
    assert sync.commit_append(preview["operation_id"], preview["preview_hash"], sheet)["status"] == "uncertain"
    assert sync.reconcile(preview["operation_id"], sheet)["status"] == "uncertain"
    assert sync.commit_append(preview["operation_id"], preview["preview_hash"], sheet)["status"] == "uncertain"
    assert sheet.appends == 1 and len(sheet.values) == 1


@pytest.mark.parametrize("failure", ["bad_range", "bad_readback"])
def test_provider_response_without_correct_readback_never_marks_committed(failure):
    sheet = Sheet(); setattr(sheet, failure, True)
    preview = sync.prepare_append(reviewed(), sheet)
    assert sync.commit_append(preview["operation_id"], preview["preview_hash"], sheet)["status"] == "uncertain"
    assert sheet.appends == 1


def test_expired_claim_requires_reconciliation_never_another_append():
    sheet = Sheet(); preview = sync.prepare_append(reviewed(), sheet)
    operation = sync._operation(preview["operation_id"])
    token = sync._claim(operation)
    with get_session() as session:
        session.get(SourceSyncLease, (sync.tenant(), SHEET)).expires_at = \
            (sync.now() - dt.timedelta(minutes=1)).isoformat()
    assert sync.commit_append(operation.id, preview["preview_hash"], sheet)["status"] == "in_flight"
    assert sync.reconcile(operation.id, sheet)["status"] == "uncertain"
    assert sheet.appends == 0
    assert sync._finish(operation.id, "stale-token", "committed") is False


def test_schema_failures_do_not_append_and_missing_writer_never_uses_reader_credentials(monkeypatch):
    sheet = Sheet(); sheet.values[0] = ["unrelated workbook"]
    with pytest.raises(ValueError, match="schema_mismatch"):
        sync.prepare_append(reviewed(), sheet)
    assert sheet.appends == 0
    monkeypatch.delenv("ASHBEL_SHEETS_WRITER_SERVICE_ACCOUNT_JSON", raising=False)
    monkeypatch.setenv("ASHBEL_SHEETS_SERVICE_ACCOUNT_JSON", "reader-only-must-not-be-used")
    with pytest.raises(ValueError, match="writer_not_configured"):
        sync.SheetsClient()


def test_preview_disabled_and_routes_require_owner_auth(monkeypatch):
    monkeypatch.setenv("OS_API_KEY", "synthetic-api-key")
    from api.app import create_app
    with patch("scheduler.revenue_scheduler.start"):
        client = create_app().test_client()
    assert client.post("/api/source_sync/preview", json={"candidate": facts()}).status_code == 401
    monkeypatch.setenv("ASHBEL_SOURCE_SYNC_ENABLED", "false")
    response = client.post("/api/source_sync/preview", json={"candidate": facts()},
                           headers={"X-API-Key": "synthetic-api-key"})
    assert response.status_code == 503 and response.get_json()["error"] == "source_sync_disabled"


def test_public_source_observation_remains_unverified_and_is_deduplicated():
    source = discovery.sources()[0]
    content = b"<rss><channel><item><title>Aluminum construction tender</title><link>https://example.com/public/1</link></item></channel></rss>"
    result = discovery.scan_sources(fetcher=lambda _: content)
    assert result["newly_observed"] == 1 and result["crm_appended"] == 0 and result["outreach_sent"] is False
    assert discovery.scan_sources(fetcher=lambda _: content)["newly_observed"] == 0
    candidate = discovery.list_candidates()[0]
    assert candidate["status"] == "candidate_unverified" and candidate["contact_permission"] == "unverified"
    assert candidate["feed_content_sha256"] == hashlib.sha256(content).hexdigest()
    with pytest.raises(ValueError, match="unsafe"):
        discovery.parse_feed(source, b"<!DOCTYPE rss [<!ENTITY x SYSTEM 'file:///private'>]><rss/>")


def test_primary_verification_fetches_actual_bytes_and_does_not_grant_contact_permission():
    content = b"<rss><channel><item><title>Aluminum tender</title><link>https://example.com/public/SYNTHETIC-1</link></item></channel></rss>"
    discovery.scan_sources(fetcher=lambda _: content)
    task = discovery.list_candidates()[0]
    with pytest.raises(ValueError, match="specific_source_review_required"):
        discovery.verify_candidate(task["task_id"], facts(), False)
    primary = b"<html>Actual synthetic primary-source content</html>"
    verified = discovery.verify_candidate(task["task_id"], facts(), True, fetcher=lambda _: primary)
    assert verified["verification"]["content_sha256"] == hashlib.sha256(primary).hexdigest()
    assert verified["verification"]["content_sha256"] != hashlib.sha256(content).hexdigest()
    assert sync.validate_candidate(verified["candidate"])["contact_permission"] == "unverified"
    assert verified["crm_saved"] is False


def test_discovery_failure_and_unconfigured_states_do_not_report_business_success(monkeypatch):
    result = discovery.scan_sources(fetcher=lambda _: (_ for _ in ()).throw(PermissionError("private")))
    assert result["status"] == "unavailable" and "private" not in json.dumps(result)
    monkeypatch.setenv("ASHBEL_PUBLIC_SOURCE_FEEDS_JSON", "[]")
    assert discovery.scan_sources()["status"] == "not_configured"
    monkeypatch.setenv("ASHBEL_SOURCE_DISCOVERY_ENABLED", "false")
    assert discovery.scan_sources()["status"] == "disabled"


def test_existing_daily_source_slot_uses_governed_candidate_queue():
    from scheduler.revenue_scheduler import _job_maps_scan
    with patch("services.integrations.source_discovery.scan_sources", return_value={"status": "observed"}) as scan:
        assert _job_maps_scan()["status"] == "observed"
        scan.assert_called_once()


def test_extended_source_adapter_separates_entity_types_from_sales_proposals():
    from services.integrations.business_source import interpret_snapshot, WORK_HEADERS
    customer = [""]*44
    for header, value in {"שם הלקוח":"Synthetic customer", "מזהה ליד":"c1", "סטטוס":"חדש",
                          "מצב הצעת מחיר":"טיוטה", "סוג ישות":"לקוח", "קטגוריית מקור":"חיצוני"}.items():
        customer[sync.HEADERS.index(header)] = value
    supplier = customer.copy(); supplier[7] = "Synthetic supplier"; supplier[12] = "s1"; supplier[31] = "ספק"
    payload = {"valueRanges":[{"values":[list(sync.HEADERS), customer, supplier]},
                              {"values":[list(WORK_HEADERS), ["מעקבי לידים"]]}]}
    result = interpret_snapshot(payload, SHEET, sync.now().isoformat())
    assert result["lead_count"] == 2 and result["entity_counts"]["ספק"] == 1
    assert result["proposal_lead_facts_total"] == 1
    assert result["proposal_lead_facts"][0]["source_category"] == "חיצוני"


def test_committed_crm_write_publishes_event_and_event_retry_never_repeats_append():
    sheet = Sheet()
    preview = sync.prepare_append(reviewed(), sheet)
    with patch("services.business_events.runtime.ingest_event", side_effect=RuntimeError("private")):
        result = sync.commit_append(preview["operation_id"], preview["preview_hash"], sheet)
    assert result["status"] == "committed" and result["result"]["business_event_status"] == "pending_retry"
    assert sheet.appends == 1
    with patch("services.business_events.runtime.ingest_event",
               return_value={"id": "synthetic-event-id", "status": "pending"}) as publish:
        result = sync.commit_append(preview["operation_id"], preview["preview_hash"], sheet)
    assert result["result"]["business_event_id"] == "synthetic-event-id"
    assert sheet.appends == 1
    assert publish.call_args.args[0]["facts"]["contact_permission"] == "unverified"


def test_crm_action_date_is_a_sheet_date_number_and_formula_text_is_not_executed():
    candidate = reviewed()
    row = sync.crm_row(sync.validate_candidate(candidate))
    assert isinstance(row[2], int)
    assert sync._row_equal([str(value) for value in row], row)
    candidate = sync.candidate_fields(facts())
    candidate["name"] = "=SYNTHETIC_FORMULA()"
    assert sync.crm_row(candidate)[7] == "=SYNTHETIC_FORMULA()"


def test_duplicate_evidence_keeps_real_row_number_across_blank_rows():
    candidate = reviewed()
    existing = [""] * 44
    existing[12], existing[28] = "existing-after-blank", candidate["source_url"]
    sheet = Sheet([[], existing])
    result = sync.prepare_append(candidate, sheet)
    assert result["status"] == "duplicate" and result["duplicate"]["row_hint"] == 3


def test_expired_unused_preview_and_before_write_failure_can_be_prepared_again():
    sheet = Sheet(); candidate = reviewed()
    preview = sync.prepare_append(candidate, sheet)
    with get_session() as session:
        session.get(SourceSyncOperation, preview["operation_id"]).expires_at = \
            (sync.now() - dt.timedelta(minutes=1)).isoformat()
    renewed = sync.prepare_append(candidate, sheet)
    assert renewed["status"] == "prepared" and renewed["expires_at"] > sync.now().isoformat()
    with patch.object(sheet, "read", side_effect=PermissionError("private")):
        failed = sync.commit_append(renewed["operation_id"], renewed["preview_hash"], sheet)
    assert failed["status"] == "read_failed" and sheet.appends == 0
    prepared = sync.prepare_append(candidate, sheet)
    assert prepared["status"] == "prepared"
    assert sync.commit_append(prepared["operation_id"], prepared["preview_hash"], sheet)["status"] == "committed"
    assert sheet.appends == 1


@pytest.mark.parametrize("published", ["", None])
def test_unknown_source_publication_date_stays_missing_and_review_hash_remains_consistent(published):
    raw = facts(); raw["published_at"] = published; raw["city"] = "לא אומת"
    normalized = sync.candidate_fields(raw)
    assert normalized["published_at"] == "" and "published_at" in normalized["missing_fields"]
    assert "city" in normalized["missing_fields"] and normalized["quality"] == "לא סווגה — חסרים נתונים"
    assert sync.crm_row(normalized)[1].startswith("מועמד חיצוני")
    assert sync.crm_row(normalized)[40] == ""
    assert sync.digest(normalized) == sync.digest(sync.candidate_fields(normalized))


def test_readonly_reconciliation_also_publishes_event():
    sheet = Sheet(); preview = sync.prepare_append(reviewed(), sheet)
    sheet.timeout_after = True
    assert sync.commit_append(preview["operation_id"], preview["preview_hash"], sheet)["status"] == "uncertain"
    with patch("services.business_events.runtime.ingest_event",
               return_value={"id":"reconciled-event", "status":"pending"}) as publish:
        result = sync.reconcile(preview["operation_id"], sheet)
    assert result["result"]["business_event_id"] == "reconciled-event"
    publish.assert_called_once()
    assert sheet.appends == 1


def test_publication_failure_is_durable_and_existing_job_retries_without_sheet_access(monkeypatch):
    sheet = Sheet(); preview = sync.prepare_append(reviewed(), sheet)
    with patch("services.business_events.runtime.ingest_event", side_effect=RuntimeError("private")):
        sync.commit_append(preview["operation_id"], preview["preview_hash"], sheet)
    assert sync._operation(preview["operation_id"]).result["business_event_status"] == "pending_retry"
    monkeypatch.setenv("ASHBEL_BUSINESS_EVENTS_ENABLED", "true")
    from scheduler.revenue_scheduler import _job_followup
    with patch("services.business_events.runtime.ingest_event",
               return_value={"id":"retried-event", "status":"pending"}), \
         patch("services.business_events.runtime.poll_source_and_process", return_value={"results":[]}), \
         patch("services.integrations.source_sync._client", side_effect=AssertionError("must not access Sheets")):
        assert _job_followup() == {"results":[]}
    assert sync._operation(preview["operation_id"]).result["business_event_id"] == "retried-event"
    assert sheet.appends == 1


def test_company_mode_never_falls_back_to_a_parallel_local_crm(monkeypatch):
    monkeypatch.setenv("ASHBEL_BUSINESS_EVENTS_ENABLED", "true")
    monkeypatch.setenv("ASHBEL_SOURCE_DISCOVERY_ENABLED", "false")
    from scheduler.revenue_scheduler import _job_maps_scan, _job_gmail_scan
    with patch("services.integrations.lead_scraper.scrape", side_effect=AssertionError("legacy CRM")), \
         patch("services.integrations.gmail_listener.scan_inbox", side_effect=AssertionError("legacy CRM")):
        assert _job_maps_scan()["status"] == "blocked"
        assert _job_gmail_scan()["status"] == "blocked"


def test_feed_connection_is_pinned_to_checked_ip_with_original_hostname_and_no_retry(monkeypatch):
    import urllib3
    class Response:
        status = 200
        def stream(self, *args, **kwargs): return iter([b"<rss/>"])
        def close(self): pass
    class Pool:
        def request(self, *args, **kwargs):
            assert kwargs["headers"]["Host"] == "example.com"
            assert kwargs["retries"] is False and kwargs["redirect"] is False
            return Response()
        def close(self): pass
    addresses = [(2, 1, 6, "", ("8.8.8.8", 443))]
    with patch("services.integrations.source_discovery.socket.getaddrinfo", side_effect=[addresses, AssertionError("second DNS resolution")]) as dns, \
         patch.object(urllib3, "HTTPSConnectionPool", return_value=Pool()) as pool:
        assert discovery._fetch({"url":"https://example.com/feed"}) == b"<rss/>"
    dns.assert_called_once()
    assert pool.call_args.args[0] == "8.8.8.8"
    assert pool.call_args.kwargs["server_hostname"] == "example.com"
    assert pool.call_args.kwargs["assert_hostname"] == "example.com"
    with patch("services.integrations.source_discovery.socket.getaddrinfo",
               return_value=[(2, 1, 6, "", ("127.0.0.1", 443))]), \
         patch.object(urllib3, "HTTPSConnectionPool", side_effect=AssertionError("private connection")):
        with pytest.raises(ValueError, match="not_public"):
            discovery._fetch({"url":"https://example.com/feed"})


def test_viewer_preview_and_writer_commit_share_unformatted_date_currency_snapshot(monkeypatch):
    historical = [""] * 44
    historical[2], historical[7], historical[12], historical[23] = 46343, "Synthetic existing", "S-OLD", 1234.5
    sheet = Sheet([historical])
    formatted = copy.deepcopy(sheet.values)
    formatted[1][2], formatted[1][23] = "17/11/2026", "₪1,234.50"
    monkeypatch.setenv("ASHBEL_SHEETS_SERVICE_ACCOUNT_JSON", "synthetic-viewer-only")

    def read_values(spreadsheet_id, value_render_option="FORMATTED_VALUE"):
        assert spreadsheet_id == SHEET
        assert sync.READ_RANGE == "'לידים'!A1:AR2000"
        from services.integrations.business_source import LEADS_RANGE
        assert LEADS_RANGE == sync.READ_RANGE
        return {"valueRanges": [{"values": sheet.read() if value_render_option == "UNFORMATTED_VALUE" else formatted}]}

    with patch("services.integrations.business_source._read_values", side_effect=read_values):
        prepared = sync.prepare_append(reviewed())
    result = sync.commit_append(prepared["operation_id"], prepared["preview_hash"], client=sheet)
    assert result["status"] == "committed"
    assert sheet.appends == 1
