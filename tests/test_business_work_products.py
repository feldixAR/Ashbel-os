"""Business artifacts and durable follow-up acceptance checks; synthetic records."""
import copy
import json
import os
import uuid
from unittest.mock import patch

import pytest

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("ENVIRONMENT", "test")

from services.business_events.work_products import finance_review, engineering_review, purchase_comparison, number
from services.business_events import runtime as rt
from services.business_events.work_items import list_work_items, review_work_item
from services.storage.db import create_all_tables, get_session
from services.storage.models.task import TaskModel


@pytest.fixture(autouse=True)
def isolated_business(monkeypatch):
    monkeypatch.setenv("BUSINESS_ID", "synthetic-" + uuid.uuid4().hex)
    monkeypatch.setenv("ASHBEL_BUSINESS_EVENTS_ENABLED", "true")
    monkeypatch.setenv("ASHBEL_BUSINESS_LLM_ADVICE_ENABLED", "false")
    create_all_tables()


def envelope(key="synthetic"):
    return dict(source="synthetic", source_event_id=key, event_type="quote.received",
                source_ref="https://example.invalid/quote", occurred_at="2026-11-17T00:00:00+00:00",
                facts={"project_id": "synthetic-project"})


def context():
    return dict(health="read_ok", snapshot_sha256="synthetic-sha", capacity_state="unknown",
                lead_count=1, work_count=0, decisions=[], actions=[], source_ranges=[])


def quote(ident="p1"):
    return dict(quote_id=ident, supplier_id=ident, verified=True, source_ref="https://example.invalid/" + ident,
                scope_hash="same-openings", scope="manufacturing_only", price_kind="contractor_purchase",
                currency="ILS", vat_basis="excluding_vat", manufacturing_ils=60,
                installation_ils=20, ancillary_ils=5, payment_terms="30/40/30", warranty="documented")


def contract():
    return dict(verified=True, source_ref="https://example.invalid/signed", currency="ILS",
                vat_basis="excluding_vat", document_kind="signed_customer_contract", selling_price_ils=100)


def test_historical_selling_prices_are_not_procurement_or_collection():
    out = finance_review({"historical_sale_quotes": [{"total_ils": 100000}],
                          "purchase_quotes": [{**quote(), "price_kind": "historical_sale"}]})
    assert out["signed_sale_ex_vat_ils"] is None
    assert out["scenarios"][0]["gross_contribution_ex_vat_ils"] is None
    assert out["recorded_collection_ils"] is None
    assert out["business_net_profit_ils"] is None


def test_finance_computes_contribution_only_with_comparable_source_backed_costs():
    facts = dict(contract=contract(), purchase_quotes=[quote()])
    out = finance_review(facts)
    assert out["scenarios"][0]["gross_contribution_ex_vat_ils"] == "15.00"
    assert out["scenarios"][0]["gross_margin_percent"] == "15.00"
    assert out["business_net_profit_ils"] is None
    assert out["monthly_operating_profit_target_ils"] == "100000.00"
    for key in ("installation_ils", "ancillary_ils", "source_ref", "warranty", "payment_terms"):
        broken = copy.deepcopy(facts)
        broken["purchase_quotes"][0].pop(key)
        assert finance_review(broken)["scenarios"][0]["gross_contribution_ex_vat_ils"] is None


def test_negative_contribution_and_receipts_are_explicit_not_net_profit():
    q = quote(); q["manufacturing_ils"] = 100
    facts = dict(contract=contract(), purchase_quotes=[q], collections=[
        dict(amount_ils=30, currency="ILS", verified=True, document_kind="payment_receipt",
             source_ref="https://example.invalid/receipt")])
    out = finance_review(facts)
    assert out["scenarios"][0]["gross_contribution_ex_vat_ils"] == "-25.00"
    assert out["recorded_collection_ils"] == "30.00"
    assert out["business_net_profit_ils"] is None
    assert number(True) is None and number("NaN") is None and number("-1") is None


def test_purchase_scope_difference_prevents_comparable_shortcut():
    q = quote("p2");q["scope_hash"] = "different-openings"
    assert not purchase_comparison({"purchase_quotes": [quote(), q]})["same_scope_comparison_available"]
    q["scope_hash"] = "same-openings"
    assert purchase_comparison({"purchase_quotes": [quote(), q]})["same_scope_comparison_available"]
    assert purchase_comparison({"purchase_quotes": [quote(), q]})["selected_supplier"] is None


def test_engineering_opens_gaps_and_replays_nominal_area_without_series_claim():
    facts = dict(specification_approved=True, quote_lines=[
        dict(line_id="s1", quantity=2, width_mm=3000, height_mm=2000,
             system="synthetic-system", glass="synthetic-glass", source_ref="https://example.invalid/spec")])
    out = engineering_review(facts)
    assert out["opening_schedule"][0]["nominal_area_m2"] == "12.00"
    assert out["production_ready"] is False
    assert set(out["missing"]) == {"manufacturer_size_load_glass_compatibility", "verified_site_measurements"}
    assert out["automatic_series_substitution"] is False


def test_event_artifacts_persist_as_open_work_and_replay_does_not_duplicate():
    eid = rt.ingest_event(envelope())["id"]
    result = rt.process_event(eid, context=context())
    assert result["status"] == "analyzed"
    event = rt.get_event(eid)
    items = list_work_items()
    assert len(items) == len(event["output"]["departments"])
    assert len({item["id"] for item in items}) == len(items)
    assert all(item["status"] in {"blocked", "created", "approval_pending"} for item in items)
    assert all(item["artifact"]["title"] and not item["independently_verified"] for item in items)
    assert event["output"]["work_item_ids"] == event["output"]["ceo_decision"]["work_item_ids"]
    assert rt.process_event(eid, context=context())["status"] == "not_claimed"
    assert {item["id"] for item in list_work_items()} == {item["id"] for item in items}


def test_owner_report_is_not_verified_completion_and_has_cas_and_audit():
    eid = rt.ingest_event(envelope())["id"];rt.process_event(eid, context=context())
    item = list_work_items()[0]
    with pytest.raises(ValueError, match="completion_evidence_ref_required"):
        review_work_item(item["id"], "report_complete", 1, "synthetic report")
    updated = review_work_item(item["id"], "report_complete", 1, "synthetic report", "https://example.invalid/report")
    assert updated["status"] == "reported_complete"
    assert updated["completion_evidence"]["kind"] == "owner_reported"
    assert updated["independently_verified"] is False
    with pytest.raises(ValueError, match="version_conflict"):
        review_work_item(item["id"], "cancel", 1, "stale")
    with get_session() as session:
        reviews = session.query(TaskModel).filter_by(type="business_work_item_review", parent_task_id=item["id"]).all()
        assert len(reviews) == 1 and reviews[0].output_data["external_action_executed"] is False


def test_work_is_tenant_scoped_and_new_source_does_not_silently_close_loop(monkeypatch):
    event = envelope();eid = rt.ingest_event(event)["id"];rt.process_event(eid, context=context())
    before = list_work_items()
    monkeypatch.setenv("BUSINESS_ID", "unrelated-synthetic")
    assert list_work_items() == []
    with pytest.raises(LookupError):
        review_work_item(before[0]["id"], "cancel", 1, "not this tenant")


def test_stale_worker_cannot_create_followup_work():
    eid = rt.ingest_event(envelope())["id"]
    token = rt._claim(eid, rt.now())
    assert token
    assert rt._finish(eid, "not-the-token", status="analyzed", output={"departments": {}}) is False
    assert list_work_items() == []


def test_advice_no_key_never_calls_router_and_unproven_refs_fail_closed(monkeypatch):
    from services.business_events.advisory import advise
    monkeypatch.setenv("ASHBEL_BUSINESS_LLM_ADVICE_ENABLED", "true")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with patch("routing.model_router.model_router.call") as call:
        assert advise("sales", envelope(), {})["status"] == "not_configured"
        call.assert_not_called()
        monkeypatch.setenv("ANTHROPIC_API_KEY", "synthetic-not-a-secret")
        call.return_value = json.dumps(dict(summary="draft", observations=[
            dict(claim="unsupported", source_refs=["https://example.invalid/not-supplied"])], next_question=""))
        assert advise("sales", envelope(), {})["status"] == "provider_or_schema_failed"
        call.return_value = json.dumps(dict(summary="draft", observations=[
            dict(claim="source claim", source_refs=[envelope()["source_ref"]])], next_question="one question"))
        result = advise("sales", envelope(), {})
        assert result["status"] == "draft_advice" and result["business_execution"] is False


def test_authenticated_poll_and_work_review_do_not_execute_external_actions(monkeypatch):
    monkeypatch.setenv("OS_API_KEY", "synthetic-key")
    from api.app import create_app
    with patch("scheduler.revenue_scheduler.start"):
        client = create_app().test_client()
    assert client.get("/api/business_events/work_items").status_code == 401
    headers = {"X-API-Key": "synthetic-key"}
    with patch("services.integrations.business_source.load_business_context",
               return_value={"health": "not_configured", "actions": []}):
        result = client.post("/api/business_events/poll", headers=headers).get_json()["data"]
    assert result["source_health"] == "not_configured" and result["results"] == []
    assert rt.recent_events() == []
    eid = rt.ingest_event(envelope())["id"];rt.process_event(eid, context=context())
    item = client.get("/api/business_events/work_items", headers=headers).get_json()["data"]["items"][0]
    response = client.post("/api/business_events/work_items/" + item["id"] + "/review", headers=headers,
                           json=dict(action="cancel", expected_version=item["version"], note="cancel synthetic"))
    assert response.status_code == 200
    assert response.get_json()["data"]["external_action_executed"] is False


def test_new_source_reopens_changed_artifact_without_duplicate_tasks_or_verified_completion():
    original = envelope("first-observation")
    eid = rt.ingest_event(original)["id"];rt.process_event(eid, context=context())
    items = list_work_items()
    pmo = next(item for item in items if item["department"] == "pmo")
    review_work_item(pmo["id"], "report_complete", pmo["version"], "owner report", "https://example.invalid/report")
    newer = envelope("second-observation");newer["occurred_at"] = "2026-11-17T00:01:00+00:00"
    next_context = context()
    next_context["actions"] = [dict(subject="synthetic-open-loop", action="verify quote", owner="synthetic-owner",
                                     due_date="2026-11-18", disposition="actionable", kind="supplier",
                                     blocked_reasons=[], evidence={"range": "synthetic"})]
    new_id = rt.ingest_event(newer)["id"]
    assert rt.process_event(new_id, context=next_context)["status"] == "analyzed"
    updated = list_work_items()
    assert {item["id"] for item in updated} == {item["id"] for item in items}
    pmo_now = next(item for item in updated if item["id"] == pmo["id"])
    assert pmo_now["status"] == "created"
    assert pmo_now["version"] == pmo["version"] + 2
    assert pmo_now["completion_evidence"] is None and pmo_now["independently_verified"] is False
    assert pmo_now["artifact"]["open_loops"][0]["subject"] == "synthetic-open-loop"


def test_auditor_rejects_forged_artifact_execution_and_financial_truth():
    from services.business_events.departments import DepartmentExpert
    event = {**envelope(), "id": "synthetic-id", "fingerprint": "synthetic-fingerprint"}
    result = DepartmentExpert("auditor").analyze(event, context(), {
        "departments": {"engineering": {
            "mode": "native_deterministic", "evidence": {"source_ref": event["source_ref"]},
            "artifact": {"production_ready": True, "business_net_profit_ils": "90000",
                         "advisory": {"business_execution": True}}}},
        "ceo_decision": {"code": "review_open_work", "executed_external_action": False, "collected_ils": None}})
    assert result["passed"] is False
    assert set(result["violations"]) == {"net_profit_not_proven", "advice_crossed_execution_boundary",
                                         "production_without_source_gates"}


@pytest.mark.parametrize("key,value", [("purchase_quotes", None), ("quote_lines", "not-a-list"),
                                       ("contract", []), ("collections", [7])])
def test_malformed_source_fact_shapes_are_rejected_before_execution(key, value):
    event = envelope();event["facts"][key] = value
    with pytest.raises(ValueError, match="invalid_" + key):
        rt.ingest_event(event)
    assert rt.recent_events() == [] and list_work_items() == []
