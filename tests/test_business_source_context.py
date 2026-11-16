"""Synthetic Sheets evidence; no network, credentials or customer records."""
import copy
from unittest.mock import patch

import pytest

from services.integrations.business_source import (
    WORK_HEADERS, LEAD_HEADERS, interpret_snapshot, load_business_context, context_plan,
)


def fixture():
    return {"valueRanges": [
        {"values": [list(LEAD_HEADERS), ["דוגמה סינתטית", "synthetic-1", "טיוטה מאושרת", "בדיקה", "לא נשלח"]]},
        {"values": [list(WORK_HEADERS),
                    ["ספק סינתטי", "הכשרת ספק חלופי", "2026-11-16", "ספק חסום", "בעלים", "אין יכולת תמחור", "fixture:capacity", "תפעול"],
                    ["פרויקט סינתטי", "תמחור מתקדם", "", "ממתין לאולם", "בעלים", "בחירת מפרט", "fixture:spec", "תפעול"],
                    ["שיווק", "הרחבת לידים", "", "פתוח", "בעלים", "", "fixture:growth", "שיווק"],
                    ["מעקבי לידים — מתעדכן אוטומטית מהלידים לפי תאריך פעולה"],
                    ["שם לקוח", "טלפון", "מועד חזרה", "פעולה ב־CRM", "הערות אחרונות"],
                    ["לא משימה נוספת", "000", "", "", ""]]},
    ]}


def snapshot():
    return interpret_snapshot(fixture(), "synthetic-sheet-identifier", "2026-11-16T12:00:00+00:00")


def test_bounded_source_evidence_and_idempotent_fingerprint():
    result = snapshot()
    assert result["work_count"] == 3  # dynamic CRM section is not another queue
    assert result["snapshot_sha256"] == snapshot()["snapshot_sha256"]
    assert result["source_updated_at"] is None
    assert result["source_freshness"] == "not_verified"
    assert result["decisions"][0]["evidence"]["range"] == "'תור עבודה'!A2:H2"
    assert result["lead_count"] == 1


def test_capacity_spec_delivery_and_money_boundaries():
    result = snapshot()
    assert result["lead_acquisition_allowed"] is False
    assert {d["code"] for d in result["decisions"]} == {"supplier_capacity_blocked", "specification_pending"}
    plan = context_plan(result)
    assert [a["action"] for a in plan["priority_items"]] == ["הכשרת ספק חלופי"]
    assert "קיבולת" in plan["top_action"]
    assert result["financial_truth"]["collected_commission_ils"] is None
    assert result["delivery_truth"] == "approved_draft_is_not_sent"


def test_schema_and_missing_boundary_fail_closed():
    data = fixture()
    data["valueRanges"][1]["values"] = data["valueRanges"][1]["values"][:4]
    with pytest.raises(ValueError, match="boundary_missing"):
        interpret_snapshot(data, "synthetic", "2026-11-16T12:00:00+00:00")
    data = fixture()
    data["valueRanges"][0]["values"][0][0] = "unknown header"
    with pytest.raises(ValueError, match="schema_mismatch"):
        interpret_snapshot(data, "synthetic", "2026-11-16T12:00:00+00:00")


def test_duplicate_and_truncated_sources_rejected():
    data = fixture()
    data["valueRanges"][0]["values"].append(copy.copy(data["valueRanges"][0]["values"][1]))
    with pytest.raises(ValueError, match="duplicate_lead_ids"):
        interpret_snapshot(data, "synthetic", "2026-11-16T12:00:00+00:00")
    data = fixture()
    data["valueRanges"][0]["values"] *= 600
    with pytest.raises(ValueError):
        interpret_snapshot(data, "synthetic", "2026-11-16T12:00:00+00:00")


def test_disabled_and_unconfigured_do_not_contact_google(monkeypatch):
    monkeypatch.setenv("ASHBEL_SOURCE_CONTEXT_ENABLED", "false")
    with patch("services.integrations.business_source._read_values") as remote:
        assert load_business_context()["health"] == "disabled"
        monkeypatch.setenv("ASHBEL_SOURCE_CONTEXT_ENABLED", "true")
        monkeypatch.delenv("ASHBEL_SHEETS_SERVICE_ACCOUNT_JSON", raising=False)
        assert load_business_context()["health"] == "not_configured"
        remote.assert_not_called()


def test_provider_error_is_redacted_and_never_falls_back_to_optimistic_plan(monkeypatch):
    monkeypatch.setenv("ASHBEL_SOURCE_CONTEXT_ENABLED", "true")
    monkeypatch.setenv("ASHBEL_SOURCE_SPREADSHEET_ID", "synthetic-sheet-identifier")
    monkeypatch.setenv("ASHBEL_SHEETS_SERVICE_ACCOUNT_JSON", "synthetic-not-a-credential")
    with patch("services.integrations.business_source._read_values", side_effect=RuntimeError("SECRET")):
        context = load_business_context()
    assert context["health"] == "unavailable"
    assert "SECRET" not in str(context)
    assert context_plan(context)["priority_items"] == []


def test_existing_daily_plan_uses_source_without_local_crm(monkeypatch):
    monkeypatch.setenv("ASHBEL_SOURCE_CONTEXT_ENABLED", "true")
    from services.crm.daily_plan import build_daily_plan
    with patch("services.integrations.business_source.load_business_context", return_value=snapshot()), \
         patch("services.crm.daily_plan._load_active_deals", side_effect=AssertionError("duplicate CRM read")):
        plan = build_daily_plan().to_dict()
    assert plan["business_context"]["health"] == "read_ok"
    assert plan["pipeline_value"] is None
    assert plan["total_deals"] is None
    assert plan["total_leads"] == 1


def test_source_change_changes_fingerprint():
    data = fixture()
    data["valueRanges"][1]["values"][1][1] = "בדיקת קיבולת חדשה"
    assert interpret_snapshot(data, "synthetic", "2026-11-16T12:00:00+00:00")["snapshot_sha256"] != snapshot()["snapshot_sha256"]


def test_closed_supplier_task_does_not_block_new_capacity():
    data = fixture()
    data["valueRanges"][1]["values"][1][3] = "הושלם"
    context = interpret_snapshot(data, "synthetic", "2026-11-16T12:00:00+00:00")
    assert context["capacity_state"] == "unknown"
    assert context["lead_acquisition_allowed"] is False


def test_unknown_capacity_never_becomes_permission():
    data = fixture()
    row = data["valueRanges"][1]["values"][1]
    row[0:6] = ["מועמדים לספקים", "בדיקת חלופה", "", "פתוח", "בעלים", "טרם נוצר קשר או הוכשרה חלופה"]
    context = interpret_snapshot(data, "synthetic", "2026-11-16T12:00:00+00:00")
    assert context["capacity_state"] == "unknown"
    assert context["lead_acquisition_allowed"] is False
    row[3] = "קיבולת ספק מאומתת"
    assert interpret_snapshot(data, "synthetic", "2026-11-16T12:00:00+00:00")["capacity_state"] == "confirmed"


def test_negative_approval_is_not_approval():
    data = fixture()
    data["valueRanges"][1]["values"][2][3] = "מפרט טרם אושר"
    result = interpret_snapshot(data, "synthetic", "2026-11-16T12:00:00+00:00")
    assert any(d["code"] == "specification_pending" for d in result["decisions"])
    assert "תמחור מתקדם" not in [a["action"] for a in context_plan(result)["priority_items"]]


def test_proposal_facts_exclude_unprepared_and_report_truncation():
    data = fixture()
    headers = data["valueRanges"][0]["values"][0]
    headers.append("מצב הצעת מחיר")
    data["valueRanges"][0]["values"][1].append("טרם הוכנה")
    for i in range(27):
        data["valueRanges"][0]["values"].append(["לקוח סינתטי", f"s-{i}", "בטיפול", "בדיקה", "", "טיוטה מאושרת"])
    context = interpret_snapshot(data, "synthetic", "2026-11-16T12:00:00+00:00")
    assert context["proposal_lead_facts_total"] == 27
    assert context["proposal_lead_facts_truncated"] == 2
    assert len(context["proposal_lead_facts"]) == 25
    assert all(x["proposal_status"] == "טיוטה מאושרת" and x["delivery"] == "not_verified" for x in context["proposal_lead_facts"])


def test_command_daily_plan_uses_read_only_context(monkeypatch):
    monkeypatch.setenv("ASHBEL_SOURCE_CONTEXT_ENABLED", "true")
    from services.execution.executor import _handle_daily_plan
    with patch("services.integrations.business_source.load_business_context", return_value=snapshot()), \
         patch("engines.outreach_engine.outreach_engine.build_daily_summary", side_effect=AssertionError("old CRM")):
        result = _handle_daily_plan(None)
    assert result.success is True
    assert result.output["business_context"]["health"] == "read_ok"
    assert [x["action"] for x in result.output["priority_items"]] == ["הכשרת ספק חלופי"]


def test_scheduler_uses_same_context_and_no_outreach(monkeypatch):
    monkeypatch.setenv("ASHBEL_SOURCE_CONTEXT_ENABLED", "true")
    from scheduler.revenue_scheduler import _job_daily_plan
    with patch("services.integrations.business_source.load_business_context", return_value=snapshot()), \
         patch("engines.outreach_engine.outreach_engine.build_daily_summary", side_effect=AssertionError("old CRM")), \
         patch("events.event_bus.event_bus.publish") as publish, \
         patch("scheduler.revenue_scheduler._record_last_run") as record:
        _job_daily_plan()
    assert publish.call_args.kwargs["payload"]["plan"]["business_context"]["health"] == "read_ok"
    record.assert_called_once_with("daily_plan")


def test_supplier_remediation_is_not_customer_spec_and_ranks_first():
    data = fixture()
    rows = data["valueRanges"][1]["values"]
    supplier = rows.pop(1)
    supplier[1] = "הכשרת חלופה ובדיקת יכולת תמחור"
    supplier[3] = "פתוח"
    supplier[5] = "מועמדים טרם נוצר קשר; לקוחות ממתינים לביקור באולם"
    # Put remediation after ten other valid tasks: the 10-item projection must
    # still promote capacity, without confusing incidental showroom notes.
    for i in range(11):
        rows.insert(1, [f"תפעול סינתטי {i}", "בדיקה פנימית", "", "פתוח", "בעלים", "", "fixture:other", "תפעול"])
    rows.insert(14, supplier)
    context = interpret_snapshot(data, "synthetic", "2026-11-16T12:00:00+00:00")
    task = next(a for a in context["actions"] if a["kind"] == "supplier")
    assert context["capacity_state"] == "unknown"
    assert task["disposition"] == "actionable"
    assert task["blocked_reasons"] == []
    assert not any(d["code"] == "specification_pending" and d["subject"] == task["subject"] for d in context["decisions"])
    assert context_plan(context)["priority_items"][0] == task


def test_future_waiting_and_review_tasks_preserved_but_not_proposed_now():
    data = fixture()
    rows = data["valueRanges"][1]["values"]
    rows.insert(1, ["פרויקט סינתטי עתידי", "שיחת המשך", "25.11.2026 15:00", "פתוח", "בעלים", "", "fixture:future", "מכירות"])
    rows.insert(2, ["פרויקט בבדיקה", "בדיקת מסמך", "", "לא מאומת", "בעלים", "", "fixture:review", "מכירות"])
    rows.insert(3, ["מסמכים כלליים", "סידור מסמכים", "", "פתוח", "בעלים", "כולל חומר של אולם ובחירת מפרט", "fixture:docs", "ידע"])
    context = interpret_snapshot(data, "synthetic", "2026-11-16T12:00:00+00:00")
    disposition = {a["subject"]: a["disposition"] for a in context["actions"]}
    assert disposition["פרויקט סינתטי עתידי"] == "future"
    assert disposition["פרויקט בבדיקה"] == "needs_review"
    assert disposition["פרויקט סינתטי"] == "waiting"
    assert disposition["מסמכים כלליים"] == "actionable"
    assert len(context["actions"]) == 6
    assert {a["subject"] for a in context_plan(context)["priority_items"]} == {"ספק סינתטי", "מסמכים כלליים"}


def test_new_demand_held_but_existing_followup_not_held_by_capacity():
    data = fixture()
    rows = data["valueRanges"][1]["values"]
    rows.insert(1, ["משפחת דוגמה", "שיחת המשך להצעה קיימת", "2026-11-15", "פתוח", "בעלים", "", "fixture:existing", "מכירות"])
    rows.insert(2, ["לקוחות חדשים", "טיפול בליד חדש", "", "פתוח", "בעלים", "", "fixture:new", "מכירות"])
    context = interpret_snapshot(data, "synthetic", "2026-11-16T12:00:00+00:00")
    assert next(a for a in context["actions"] if a["subject"] == "לקוחות חדשים")["disposition"] == "blocked"
    assert any(a["subject"] == "משפחת דוגמה" for a in context_plan(context)["priority_items"])


def test_due_dates_use_jerusalem_and_completed_tasks_keep_evidence():
    data = fixture()
    data["valueRanges"][1]["values"][1][2] = "17.11.2026"
    context = interpret_snapshot(data, "synthetic", "2026-11-16T23:00:00+00:00")
    assert context["as_of_date_il"] == "2026-11-17"
    assert context["actions"][0]["disposition"] == "actionable"
    data["valueRanges"][1]["values"][1][3] = "הושלם"
    context = interpret_snapshot(data, "synthetic", "2026-11-16T12:00:00+00:00")
    assert context["actions"][0]["disposition"] == "completed"
    assert context["actions"][0]["evidence"]["range"] == "'תור עבודה'!A2:H2"
