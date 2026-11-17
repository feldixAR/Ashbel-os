"""Synthetic workbook/real durable event tests; never business credentials/data."""
import os
import json
from unittest.mock import patch

import pytest

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("ENVIRONMENT", "test")
from services.integrations import pricing_source as source

SHEET = "synthetic-existing-pricing-workbook-0000"
STAMP = "2026-11-17T08:00:00+00:00"


def row(line="Q-01", quote="Q", included=1):
    return [line, quote, "Synthetic project", "2026-11-16", "2", 1200, 1300, 280,
            2, "1700", "הזזה", "בידודית לפי המקור", "חשמלי לפי המקור", 1500, 3000,
            included, "הצעת קבלן ללקוח", 1, "Synthetic note", "https://example.invalid/quote.pdf"]


def values():
    return [list(source.HEADERS), row()]


def test_quote_rows_keep_source_prices_and_alternatives_separate_from_purchase_or_revenue():
    data=values()+[row("Q-ALT", included=0)]
    event=source.interpret_values(data,SHEET,STAMP)[0]
    facts=event["facts"]
    assert event["event_type"]=="quote.received"
    assert facts["project_id"]=="pricing-project:Synthetic project"
    assert len(facts["quote_lines"])==1 and len(facts["alternative_quote_lines"])==1
    line=facts["quote_lines"][0]
    assert (line["quantity"],line["width_mm"],line["height_mm"],line["shutter_box_mm"])==(2,"1200","1300","280")
    assert line["unit_price_ex_vat_ils"]=="1500" and line["source_line_total_ex_vat_ils"]=="3000"
    assert line["source_document_ref"]=="https://example.invalid/quote.pdf"
    assert "A5" in line["source_ref"]
    ref=facts["historical_sale_quotes"][0]
    assert ref["sum_included_source_lines_ex_vat_ils"]=="3000"
    assert ref["document_grand_total_verified"] is False
    assert facts["purchase_quotes"]==[] and facts["collections"]==[]
    assert "contract" not in facts and "specification_approved" not in facts


def test_missing_numbers_or_unknown_source_never_become_zero_or_verified_purchase():
    data=values()
    data[1][5],data[1][14],data[1][16],data[1][19]="", "", "", "javascript:alert(1)"
    facts=source.interpret_values(data,SHEET,STAMP)[0]["facts"]
    line=facts["quote_lines"][0]
    assert line["width_mm"] is None and line["source_line_total_ex_vat_ils"] is None
    assert line["source_document_ref"] is None
    assert {"width_mm","source_line_total_ex_vat_ils","source_document_link"}.issubset(line["missing"])
    assert line["purchase_price_verified"] is False
    assert facts["historical_sale_quotes"][0]["sum_included_source_lines_ex_vat_ils"] is None


def test_unknown_inclusion_flag_does_not_silently_sum_or_discard_line():
    data=values()+[row("Q-UNKNOWN",included="")]
    facts=source.interpret_values(data,SHEET,STAMP)[0]["facts"]
    assert len(facts["unclassified_quote_lines"])==1
    assert facts["historical_sale_quotes"][0]["sum_included_source_lines_ex_vat_ils"] is None


def test_content_identity_ignores_fetch_time_but_tracks_real_quote_changes():
    first=source.interpret_values(values(),SHEET,STAMP)[0]
    repeat=source.interpret_values(values(),SHEET,"2026-11-18T08:00:00+00:00")[0]
    assert first["source_event_id"]==repeat["source_event_id"] and first["facts"]==repeat["facts"]
    changed=values();changed[1][14]=3100
    assert source.interpret_values(changed,SHEET,STAMP)[0]["source_event_id"]!=first["source_event_id"]


def test_equivalent_unformatted_number_representations_are_not_new_quotes():
    first=source.interpret_values(values(),SHEET,STAMP)[0]
    other=values();other[1][5]=1200.0;other[1][13]="1500.00";other[1][14]=3000.0
    assert source.interpret_values(other,SHEET,STAMP)[0]["source_event_id"]==first["source_event_id"]


@pytest.mark.parametrize("mutation",["header","duplicate","project","shape","truncated"])
def test_ambiguous_or_truncated_workbooks_fail_closed(mutation):
    data=values()
    if mutation=="header":data[0][0]="wrong"
    if mutation=="duplicate":data.append(row())
    if mutation=="project":
        second=row("Q-02");second[2]="Other project";data.append(second)
    if mutation=="shape":data[1].append("extra column")
    if mutation=="truncated":data=[list(source.HEADERS)]+[[]]*1996
    with pytest.raises(ValueError):source.interpret_values(data,SHEET,STAMP)


def test_disabled_missing_credential_and_invalid_workbook_do_not_request_google(monkeypatch):
    monkeypatch.delenv("ASHBEL_PRICING_SOURCE_ENABLED",raising=False)
    with patch.object(source,"_read_values",side_effect=AssertionError("network must not run")):
        assert source.load_pricing_events()["health"]=="disabled"
        monkeypatch.setenv("ASHBEL_PRICING_SOURCE_ENABLED","true")
        monkeypatch.delenv("ASHBEL_SHEETS_SERVICE_ACCOUNT_JSON",raising=False)
        assert source.load_pricing_events()["health"]=="not_configured"
        monkeypatch.setenv("ASHBEL_SHEETS_SERVICE_ACCOUNT_JSON","synthetic-not-a-key")
        monkeypatch.setenv("ASHBEL_PRICING_SPREADSHEET_ID","../bad")
        assert source.load_pricing_events()["health"]=="unavailable"


@pytest.mark.parametrize("failure",[TimeoutError("SECRET"),PermissionError("SECRET"),ValueError("SECRET")])
def test_provider_failures_are_explicit_redacted_and_not_a_zero_quote_snapshot(monkeypatch,failure):
    monkeypatch.setenv("ASHBEL_PRICING_SOURCE_ENABLED","true")
    monkeypatch.setenv("ASHBEL_SHEETS_SERVICE_ACCOUNT_JSON","synthetic-not-a-key")
    monkeypatch.setenv("ASHBEL_PRICING_SPREADSHEET_ID",SHEET)
    with patch.object(source,"_read_values",side_effect=failure):
        result=source.load_pricing_events()
    assert result["health"]=="unavailable" and result["events"]==[]
    assert "SECRET" not in str(result) and "quote_count" not in result


def test_persistent_ingestion_replay_and_change_use_real_department_runtime(monkeypatch):
    from services.storage.db import create_all_tables,get_session
    from services.storage.models.business_event import BusinessEventModel
    from services.business_events import runtime
    monkeypatch.setenv("BUSINESS_ID","synthetic-pricing-tests")
    create_all_tables()
    with get_session() as session:
        session.query(BusinessEventModel).filter_by(business_id="synthetic-pricing-tests").delete()
    envelopes=source.interpret_values(values(),SHEET,STAMP)
    loaded={"health":"read_ok","events":envelopes}
    with patch.object(source,"load_pricing_events",return_value=loaded):
        first=source.enqueue_pricing_events();repeat=source.enqueue_pricing_events()
    assert first["queued"]==1 and repeat["duplicates"]==1
    assert first["event_ids"]==repeat["event_ids"]
    context={"health":"read_ok","snapshot_sha256":"synthetic-context-sha","capacity_state":"unknown",
             "actions":[],"decisions":[],"source_ranges":[],"lead_count":1,"work_count":0}
    assert runtime.process_event(first["event_ids"][0],context=context)["status"]=="analyzed"
    stored=runtime.get_event(first["event_ids"][0])["output"]
    assert stored["departments"]["engineering"]["artifact"]["opening_schedule"][0]["nominal_area_m2"]=="3.12"
    finance=stored["departments"]["finance"]["artifact"]
    assert finance["signed_sale_ex_vat_ils"] is None and finance["recorded_collection_ils"] is None
    assert finance["business_net_profit_ils"] is None
    assert stored["external_execution"] is False and stored["independent_auditor"]["passed"] is True
    changed=values();changed[1][14]=3100
    with patch.object(source,"load_pricing_events",return_value={"health":"read_ok","events":source.interpret_values(changed,SHEET,STAMP)}):
        update=source.enqueue_pricing_events()
    assert update["queued"]==1 and update["event_ids"]!=first["event_ids"]


def test_partial_storage_error_retains_known_event_ids_and_is_safe_to_retry(monkeypatch):
    events=source.interpret_values(values()+[row("R-01",quote="R")],SHEET,STAMP)
    with patch.object(source,"load_pricing_events",return_value={"health":"read_ok","events":events}), \
         patch("services.business_events.runtime.ingest_event",side_effect=[{"id":"one","duplicate":False},RuntimeError("SECRET")]):
        result=source.enqueue_pricing_events()
    assert result["health"]=="event_storage_unavailable" and result["event_ids"]==["one"]
    assert result["queued"]==1 and "SECRET" not in str(result)


def test_google_reader_uses_only_read_scope_fixed_range_and_no_redirects(monkeypatch):
    monkeypatch.setenv("ASHBEL_SHEETS_SERVICE_ACCOUNT_JSON",json.dumps({
        "type":"service_account","token_uri":"https://oauth2.googleapis.com/token"}))
    class Credentials:
        token="synthetic"
        def refresh(self,request): pass
    class Response:
        status_code=200
        def __enter__(self): return self
        def __exit__(self,*args): pass
        def iter_content(self,size): return iter([json.dumps({"values":values()}).encode()])
    with patch("google.oauth2.service_account.Credentials.from_service_account_info",return_value=Credentials()) as auth, \
         patch("requests.get",return_value=Response()) as get:
        assert source._read_values(SHEET)==values()
    assert auth.call_args.kwargs["scopes"]==["https://www.googleapis.com/auth/spreadsheets.readonly"]
    assert get.call_args.args[0].startswith("https://sheets.googleapis.com/v4/spreadsheets/"+SHEET+"/values/")
    assert get.call_args.kwargs["allow_redirects"] is False
    assert get.call_args.kwargs["params"]=={"valueRenderOption":"UNFORMATTED_VALUE"}
    assert get.call_args.kwargs["timeout"]==(5,15)


@pytest.mark.parametrize("change",[{"token_uri":"https://example.invalid/steal"},{"subject":"delegate@example.invalid"},{"universe_domain":"example.invalid"}])
def test_credentials_cannot_redirect_auth_or_request_domain_delegation(monkeypatch,change):
    info={"type":"service_account","token_uri":"https://oauth2.googleapis.com/token",**change}
    monkeypatch.setenv("ASHBEL_SHEETS_SERVICE_ACCOUNT_JSON",json.dumps(info))
    with patch("google.oauth2.service_account.Credentials.from_service_account_info",side_effect=AssertionError("no authentication")), \
         patch("requests.get",side_effect=AssertionError("no provider request")):
        with pytest.raises(ValueError,match="invalid_credentials"):source._read_values(SHEET)


@pytest.mark.parametrize("status",[302,403])
def test_google_redirect_or_denial_is_not_followed_or_read_as_an_empty_workbook(monkeypatch,status):
    monkeypatch.setenv("ASHBEL_SHEETS_SERVICE_ACCOUNT_JSON",json.dumps({
        "type":"service_account","token_uri":"https://oauth2.googleapis.com/token"}))
    class Credentials:
        token="synthetic"
        def refresh(self,request): pass
    class Response:
        status_code=status
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def iter_content(self,size):raise AssertionError("denied response must not be interpreted")
    with patch("google.oauth2.service_account.Credentials.from_service_account_info",return_value=Credentials()), \
         patch("requests.get",return_value=Response()) as get:
        with pytest.raises(ValueError,match="pricing_source_http_"):source._read_values(SHEET)
    assert get.call_args.kwargs["allow_redirects"] is False
