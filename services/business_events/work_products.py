"""Concrete business artifacts from bounded source facts; no provider side effects.

Numbers are computed only from explicitly source-backed, verified facts supplied
by an authorized intake adapter. This module does not verify a remote document.
Historical selling quotes remain a separate reference dataset.
"""
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP


def number(value):
    if isinstance(value, bool) or value is None:
        return None
    try:
        result = Decimal(str(value))
        return result if result.is_finite() and 0 <= result <= Decimal("1000000000") else None
    except (InvalidOperation, ValueError, TypeError):
        return None


def money(value):
    return str(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)) if value is not None else None


def source_backed(row):
    return (isinstance(row, dict) and row.get("verified") is True
            and isinstance(row.get("source_ref"), str) and bool(row["source_ref"].strip()))


def purchase_comparison(facts):
    rows = []
    for quote in facts.get("purchase_quotes", [])[:20]:
        if not isinstance(quote, dict):
            continue
        required = ("supplier_id", "scope_hash", "payment_terms", "warranty")
        missing = [key for key in required if not quote.get(key)]
        if not source_backed(quote):
            missing.append("verified_source")
        if quote.get("price_kind") != "contractor_purchase":
            missing.append("contractor_purchase_price")
        if quote.get("currency") != "ILS" or quote.get("vat_basis") != "excluding_vat":
            missing.append("comparable_currency_and_vat_basis")
        costs = {key: number(quote.get(key)) for key in
                 ("manufacturing_ils", "installation_ils", "ancillary_ils")}
        missing += [key for key, amount in costs.items() if amount is None]
        total = sum(costs.values()) if all(value is not None for value in costs.values()) else None
        rows.append({"quote_id": quote.get("quote_id"), "supplier_id": quote.get("supplier_id"),
                     "scope_hash": quote.get("scope_hash"), "scope": quote.get("scope"),
                     "source_ref": quote.get("source_ref"), "payment_terms": quote.get("payment_terms"),
                     "warranty": quote.get("warranty"), "costs_ex_vat_ils": {k: money(v) for k, v in costs.items()},
                     "total_ex_vat_ils": money(total), "eligible_for_comparison": not missing,
                     "missing": missing, "evidence_status": "source_claimed_verified" if source_backed(quote) else "unverified"})
    scopes = {row["scope_hash"] for row in rows if row["eligible_for_comparison"]}
    comparable = len(scopes) == 1 and len([r for r in rows if r["eligible_for_comparison"]]) >= 2
    return {"quotes": rows, "same_scope_comparison_available": comparable,
            "selected_supplier": None, "commitment_made": False,
            "required_request": ["manufacturing_only", "manufacturing_with_installation",
                                 "ancillary_costs", "payment_terms", "warranty", "capacity"],
            "selection": "owner_approval_required_after_scope_and_terms_review"}


def engineering_review(facts):
    schedule, missing = [], []
    for index, row in enumerate(facts.get("quote_lines", [])[:200], 1):
        if not isinstance(row, dict):
            continue
        qty, width, height = (number(row.get(key)) for key in ("quantity", "width_mm", "height_mm"))
        valid = qty is not None and qty > 0 and qty == int(qty) and width is not None and width > 0 and height is not None and height > 0
        area = qty * width * height / Decimal("1000000") if valid else None
        gaps = [key for key in ("system", "glass", "source_ref") if not row.get(key)]
        if not valid:
            gaps.append("dimensions_and_integer_quantity")
        schedule.append({"line_id": row.get("line_id", str(index)), "quantity": int(qty) if valid else None,
                         "system": row.get("system"), "glass": row.get("glass"),
                         "nominal_area_m2": money(area), "source_ref": row.get("source_ref"), "missing": gaps})
    if not schedule:
        missing.append("opening_schedule")
    if facts.get("specification_approved") is not True:
        missing.append("approved_specification")
    if not facts.get("manufacturer_specification_ref"):
        missing.append("manufacturer_size_load_glass_compatibility")
    if not facts.get("site_measurement_ref"):
        missing.append("verified_site_measurements")
    if any(row["missing"] for row in schedule):
        missing.append("opening_schedule_gaps")
    return {"opening_schedule": schedule, "missing": missing,
            "production_ready": not missing, "automatic_series_substitution": False,
            "pricing_mode": "source_replay_only_no_manufacturer_formula",
            "historical_sale_quotes": [q for q in facts.get("historical_sale_quotes", [])[:20] if isinstance(q, dict)]}


def finance_review(facts):
    comparison = purchase_comparison(facts)
    contract = facts.get("contract", {})
    sale = (number(contract.get("selling_price_ils")) if source_backed(contract)
            and contract.get("document_kind") == "signed_customer_contract"
            and contract.get("currency") == "ILS"
            and contract.get("vat_basis") == "excluding_vat" else None)
    scenarios = []
    for quote in comparison["quotes"]:
        total = number(quote["total_ex_vat_ils"])
        contribution = sale - total if sale is not None and total is not None and quote["eligible_for_comparison"] else None
        scenarios.append({"quote_id": quote["quote_id"], "supplier_id": quote["supplier_id"],
                          "scope_hash": quote["scope_hash"], "gross_contribution_ex_vat_ils": money(contribution),
                          "gross_margin_percent": money(contribution / sale * 100) if contribution is not None and sale else None,
                          "source_refs": [contract.get("source_ref"), quote.get("source_ref")],
                          "basis": "contract_less_manufacturing_installation_ancillary_not_net_profit"})
    receipts = [row for row in facts.get("collections", [])[:100] if source_backed(row)
                and row.get("document_kind") == "payment_receipt" and row.get("currency") == "ILS"
                and number(row.get("amount_ils")) is not None]
    collected = sum((number(row["amount_ils"]) for row in receipts), Decimal(0)) if receipts else None
    return {"signed_sale_ex_vat_ils": money(sale), "scenarios": scenarios,
            "recorded_collection_ils": money(collected), "collection_basis": "source_backed_receipt_facts_not_bank_reconciliation",
            "collection_source_refs": [row["source_ref"] for row in receipts],
            "business_net_profit_ils": None, "monthly_operating_profit_target_ils": "100000.00",
            "target_basis": "after_business_expenses_before_personal_tax",
            "missing": (["signed_sale_contract"] if sale is None else [])
                       + (["verified_comparable_procurement_costs"] if not any(q["eligible_for_comparison"] for q in comparison["quotes"]) else [])
                       + (["collection_evidence"] if not receipts else []),
            "cashflow_gate": "reconcile_customer_payment_schedule_with_supplier_and_installer_terms"}


def build_artifact(role, event, context):
    facts = event.get("facts", {})
    identity = {key: facts.get(key) for key in ("crm_record_id", "project_id", "supplier_id") if facts.get(key)}
    base = {"event_type": event["event_type"], "entity": identity, "source_ref": event["source_ref"],
            "evidence_basis": "authorized_intake_facts_and_existing_source_snapshot"}
    if role == "engineering":
        return {**base, **engineering_review(facts)}
    if role == "procurement":
        return {**base, **purchase_comparison(facts), "capacity_state": context.get("capacity_state")}
    if role == "finance":
        return {**base, **finance_review(facts)}
    if role == "sales":
        return {**base, "last_context": str(facts.get("last_context", facts.get("message_text", "")))[:2000],
                "contact_permission": facts.get("contact_permission", "unverified"),
                "next_step": facts.get("requested_next_step", "לאמת את הצורך והשלב לפני הצעה."),
                "draft": facts.get("draft_body"), "draft_is_approved": False, "message_sent": False}
    if role == "marketing":
        return {**base, "opportunity": {key: facts.get(key) for key in
                ("name", "city", "project_type", "project_stage", "aluminum_need", "source_published_date",
                 "quality", "confidence", "contact_permission")},
                "deduplication_required": True, "public_contact_is_consent": False,
                "research_allowed": True, "outreach_allowed": False}
    if role == "strategy":
        return {**base, "business_model": "direct_contractor",
                "required_capabilities": {"manufacturing": context.get("capacity_state"),
                                          "installation": facts.get("installer_verified", False),
                                          "commercial_liability": facts.get("commercial_terms_ref"),
                                          "cashflow": facts.get("cashflow_plan_ref")},
                "monthly_operating_profit_target_ils": "100000.00", "forecast": None}
    if role == "pmo":
        return {**base, "open_loops": [
            {key: action.get(key) for key in ("subject", "action", "owner", "due_date", "disposition", "blocked_reasons", "evidence")}
            for action in context.get("actions", []) if action.get("disposition") != "completed"][:100],
                "source_queue_is_authoritative": True, "completion_requires_evidence": True}
    if role == "knowledge":
        return {**base, "source_event_id": event.get("source_event_id"),
                "fact_fingerprint": event["fingerprint"], "snapshot_fingerprint": context.get("snapshot_sha256"),
                "source_ranges": context.get("source_ranges", []),
                "retention": "event_inbox_plus_task_evidence_not_another_crm"}
    return base
