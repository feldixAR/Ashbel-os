"""
engines/lead_acquisition_engine.py — Lead Acquisition Engine
Phase 12: Lead Acquisition OS

Orchestrating engine: business goal → source discovery → lead intel
→ outreach intel → work queue → CRM push → event publish.

Entry points:
  run_acquisition(goal, signals, session) -> AcquisitionResult
  process_inbound(lead_data, session)     -> str (lead_id)
  run_website_analysis(url, html)         -> WebsiteAnalysisResult
"""

from __future__ import annotations
import logging
import datetime
from dataclasses import dataclass, field
from typing import Any

log = logging.getLogger(__name__)


# ── Result contracts ──────────────────────────────────────────────────────────

@dataclass
class AcquisitionResult:
    goal:              str
    total_discovered:  int
    new_leads:         int
    duplicates:        int
    work_queue:        list[dict]   = field(default_factory=list)
    discovery_plan:    dict         = field(default_factory=dict)
    session_id:        str          = ""
    errors:            list[str]    = field(default_factory=list)


@dataclass
class WebsiteAnalysisResult:
    url:               str
    audit_score:       int
    lead_capture_score: int
    top_recommendations: list[str] = field(default_factory=list)
    content_gaps:      list[dict]  = field(default_factory=list)
    priority_plan:     list[dict]  = field(default_factory=list)
    seo:               dict        = field(default_factory=dict)


# ── Main entry points ──────────────────────────────────────────────────────────

def run_acquisition(
    goal: str,
    signals: list[dict[str, Any]] | None = None,
    session: Any = None,
    business_profile: dict[str, Any] | None = None,
) -> AcquisitionResult:
    """
    Full pipeline: goal → plan → normalize → dedup → enrich → score → rank
    → outreach intel → work queue → CRM push → events.

    signals: list of raw dict signals (from scraper/manual/import).
             If empty, returns the discovery plan with no candidates.
    """
    from skills.source_discovery    import discover_sources, explain_source_strategy
    from skills.lead_intelligence   import (
        extract_candidates, deduplicate, enrich, score_lead, rank_leads, explain_fit
    )
    from skills.outreach_intelligence import choose_action, draft_first_contact, draft_inbound_response
    from skills.workflow_skills      import build_work_queue, push_to_crm
    from skills.israeli_context      import geo_fit as compute_geo_fit
    from events.event_bus            import event_bus
    import events.event_types        as ET

    session_id = _session_id()
    errors: list[str] = []

    # 1. Discovery plan (always)
    plan = discover_sources(goal, business_profile)

    # 2. Normalize + dedup raw signals
    raw_signals = signals or []
    candidates = extract_candidates(raw_signals)

    existing: list[dict] = []
    if session and candidates:
        try:
            from services.storage.repositories.lead_repo import LeadRepository
            repo = LeadRepository(session)
            existing = [
                {"id": l.id, "phone": l.phone or "", "email": l.email or "",
                 "name": l.name, "company": l.company or ""}
                for l in repo.list_all(limit=500)
            ]
        except Exception as e:
            errors.append(f"existing-load: {e}")

    dedup = deduplicate(candidates, existing)

    # 3. Enrich + score + rank
    scored: list[Any] = []
    for norm in dedup.new_leads:
        try:
            enriched = enrich(norm)
            sc = score_lead(enriched)
            scored.append(sc)
        except Exception as e:
            errors.append(f"score: {e}")

    ranked = rank_leads(scored)

    # 4. Outreach intel per lead
    leads_for_queue: list[dict] = []
    for sl in ranked:
        lead_d = _scored_to_dict(sl)
        try:
            action_choice = choose_action(lead_d)
            if action_choice.action != "wait":
                draft = (draft_inbound_response(lead_d, lead_d.get("notes") or "")
                         if lead_d.get("is_inbound")
                         else draft_first_contact(lead_d, business_profile))
                lead_d["outreach_action"] = action_choice.action
                lead_d["outreach_draft"]  = draft.body
                lead_d["channel"]         = action_choice.channel
            else:
                lead_d["outreach_action"] = "wait"
        except Exception as e:
            errors.append(f"outreach: {e}")
        lead_d["discovery_session_id"] = session_id
        leads_for_queue.append(lead_d)

    # 5. Build work queue
    queue = build_work_queue(leads_for_queue)

    # 6. CRM push + events
    saved_count = 0
    if session:
        for lead_d in leads_for_queue:
            try:
                lead_id = push_to_crm(lead_d, session)
                lead_d["id"] = lead_id
                saved_count += 1
                event_bus.publish(
                    ET.LEAD_DISCOVERED,
                    payload={"lead_id": lead_id, "session_id": session_id,
                             "source_type": lead_d.get("source_type"), "score": lead_d.get("score")},
                )
            except Exception as e:
                errors.append(f"crm: {e}")

    # 7. Persist discovery session
    if session:
        _save_discovery_session(session, session_id, goal, plan, len(leads_for_queue))

    return AcquisitionResult(
        goal=goal,
        total_discovered=len(candidates),
        new_leads=len(dedup.new_leads),
        duplicates=len(dedup.duplicates),
        work_queue=[_work_item_to_dict(i) for i in queue.items],
        discovery_plan=_plan_to_dict(plan),
        session_id=session_id,
        errors=errors,
    )


def process_inbound(lead_data: dict[str, Any], session: Any = None) -> str:
    """
    Process an inbound lead (from form, Telegram, WhatsApp).
    Returns the saved lead_id.
    """
    from skills.lead_intelligence      import normalize, enrich, score_lead
    from skills.outreach_intelligence  import draft_inbound_response
    from skills.workflow_skills        import push_to_crm, update_lead_status
    from events.event_bus              import event_bus
    import events.event_types          as ET

    lead_data["is_inbound"] = True
    norm     = normalize(lead_data)
    enriched = enrich(norm)
    scored   = score_lead(enriched)

    inbound_text = lead_data.get("message") or lead_data.get("notes") or ""
    draft = draft_inbound_response(_scored_to_dict(scored), inbound_text)

    lead_dict = _scored_to_dict(scored)
    lead_dict["outreach_draft"]  = draft.body
    lead_dict["outreach_action"] = "inbound_response"
    lead_dict["is_inbound"]      = True

    lead_id = ""
    if session:
        try:
            lead_id = push_to_crm(lead_dict, session)
            event_bus.publish(
                ET.INBOUND_LEAD_RECEIVED,
                payload={"lead_id": lead_id, "score": scored.score,
                         "source": lead_data.get("source_type", "inbound")},
            )
        except Exception as e:
            log.error(f"[LeadAcquisition] inbound push failed: {e}", exc_info=True)

    return lead_id


def run_website_analysis(url: str, html: str = "") -> WebsiteAnalysisResult:
    """
    Run full website audit + SEO + content gaps + lead capture + priority plan.
    """
    from skills.website_growth import (
        site_audit, seo_intelligence, content_gap_detection,
        landing_page_suggestions, lead_capture_review, priority_planner,
    )
    from events.event_bus import event_bus
    import events.event_types as ET

    audit    = site_audit(url, html)
    seo      = seo_intelligence(audit)
    gaps     = content_gap_detection(audit)
    lc       = lead_capture_review(audit)
    tips     = landing_page_suggestions(audit)
    plan     = priority_planner(audit, gaps)

    event_bus.publish(
        ET.WEBSITE_ANALYSIS_REQUESTED,
        payload={"url": url, "audit_score": audit.raw_score, "lc_score": lc.score},
    )

    return WebsiteAnalysisResult(
        url=url,
        audit_score=audit.raw_score,
        lead_capture_score=lc.score,
        top_recommendations=tips,
        content_gaps=[{"topic": g.topic, "type": g.type, "priority": g.priority} for g in gaps[:8]],
        priority_plan=[{"title": p.title, "type": p.type, "impact": p.estimated_impact,
                        "effort": p.effort} for p in plan[:6]],
        seo={
            "missing_city_pages": seo.missing_city_pages[:5],
            "keyword_gaps":       seo.keyword_gaps[:5],
            "local_seo_score":    seo.local_seo_score,
        },
    )


# ── Private helpers ────────────────────────────────────────────────────────────

def _session_id() -> str:
    import uuid
    return f"acq-{uuid.uuid4().hex[:8]}"


def _scored_to_dict(sl: Any) -> dict:
    lead = sl.lead
    return {
        "name":           lead.name,
        "phone":          lead.phone,
        "email":          lead.email,
        "city":           lead.city,
        "company":        lead.company,
        "role":           lead.role,
        "source_type":    lead.source_type,
        "source_url":     lead.source_url,
        "segment":        lead.segment,
        "is_inbound":     lead.is_inbound,
        "score":          sl.score,
        "priority":       sl.priority,
        "fit_reasons":    sl.fit_reasons,
        "next_action":    sl.next_action,
        "geo_fit_score":  sl.geo_fit_score,
        "notes":          " | ".join(sl.fit_reasons),
    }


def _work_item_to_dict(item: Any) -> dict:
    return {
        "lead_id":           item.lead_id,
        "lead_name":         item.lead_name,
        "action":            item.action,
        "channel":           item.channel,
        "draft":             item.draft,
        "priority":          item.priority,
        "approval_required": item.approval_required,
        "approval_status":   item.approval_status,
        "notes":             item.notes,
        "due_at":            item.due_at,
    }


def _plan_to_dict(plan: Any) -> dict:
    return {
        "goal":             plan.goal,
        "segments":         plan.segments,
        "source_types":     plan.source_types,
        "communities":      [
            {"name": c.name, "source_type": c.source_type,
             "url_hint": c.url_hint, "signal_type": c.signal_type}
            for c in plan.communities[:8]
        ],
        "search_intents":   [
            {"query": i.query, "source_type": i.source_type, "priority": i.priority}
            for i in plan.search_intents[:8]
        ],
        "outreach_strategy": plan.outreach_strategy,
        "notes":            plan.notes,
    }


def _save_discovery_session(
    session: Any,
    session_id: str,
    goal: str,
    plan: Any,
    lead_count: int,
) -> None:
    try:
        from services.storage.models.lead_discovery import LeadDiscoveryModel
        ds = LeadDiscoveryModel(
            session_id=session_id,
            goal=goal,
            segments_json=str(plan.segments),
            source_types_json=str(plan.source_types),
            lead_count=lead_count,
            status="completed",
        )
        session.add(ds)
        session.flush()
    except Exception as e:
        log.warning(f"[LeadAcquisition] session save failed (non-critical): {e}")
