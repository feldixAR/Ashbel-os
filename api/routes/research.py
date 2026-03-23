from flask import Blueprint, request, jsonify
import logging
log = logging.getLogger(__name__)
bp = Blueprint("research", __name__)

@bp.route("/research/profile/<audience>", methods=["GET"])
def get_client_profile(audience):
    try:
        from engines.research_engine import build_client_profile
        p = build_client_profile(audience)
        return jsonify({"success": True, "audience": audience, "profile": {"title": p.title, "description": p.description, "pain_points": p.pain_points, "motivations": p.motivations, "objections": p.objections, "best_channels": p.best_channels, "best_times": p.best_times, "message_tone": p.message_tone, "decision_maker": p.decision_maker, "avg_deal_size": p.avg_deal_size, "buying_cycle": p.buying_cycle}})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@bp.route("/research/market/<domain>", methods=["GET"])
def get_market_map(domain):
    try:
        from engines.research_engine import build_market_map
        mm = build_market_map(domain)
        return jsonify({"success": True, "domain": domain, "market": {"market_size": mm.market_size, "growth_trend": mm.growth_trend, "players": [{"name": p.name, "strength": p.strength, "weakness": p.weakness, "our_edge": p.our_edge} for p in mm.players], "opportunities": mm.opportunities, "threats": mm.threats, "our_position": mm.our_position}})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@bp.route("/research/proposal", methods=["POST"])
def get_proposal():
    try:
        data = request.get_json() or {}
        from engines.research_engine import build_collaboration_proposal
        p = build_collaboration_proposal(data.get("audience", "general"), data.get("contact_name", ""))
        return jsonify({"success": True, "proposal": {"subject": p.subject, "opening": p.opening, "value_prop": p.value_prop, "call_to_action": p.call_to_action, "full_text": p.full_text}})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@bp.route("/research/script/<audience>", methods=["GET"])
def get_sales_script(audience):
    try:
        from engines.research_engine import build_sales_script
        s = build_sales_script(audience, request.args.get("stage", "first_contact"))
        return jsonify({"success": True, "audience": audience, "script": {"opener": s.opener, "questions": s.questions, "objections": s.objections, "closer": s.closer, "full_script": s.full_script}})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@bp.route("/research/landing/<audience>", methods=["GET"])
def get_landing_page(audience):
    try:
        from engines.research_engine import build_landing_page_copy
        lp = build_landing_page_copy(audience)
        return jsonify({"success": True, "audience": audience, "landing_page": {"headline": lp.headline, "subheadline": lp.subheadline, "benefits": lp.benefits, "social_proof": lp.social_proof, "cta": lp.cta, "full_copy": lp.full_copy}})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@bp.route("/research/portfolio/<audience>", methods=["GET"])
def get_portfolio(audience):
    try:
        from engines.research_engine import build_niche_portfolio
        po = build_niche_portfolio(audience)
        return jsonify({"success": True, "audience": audience, "portfolio": {"title": po.title, "description": po.description, "highlights": po.highlights, "projects": po.projects, "cta": po.cta}})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@bp.route("/research/package", methods=["POST"])
def get_research_package():
    try:
        data = request.get_json() or {}
        from engines.research_engine import full_research_package
        pkg = full_research_package(data.get("goal_id", ""), data.get("domain", "aluminum"), data.get("audience", "architects"), data.get("channel", "whatsapp"))
        return jsonify({"success": True, "created_at": pkg.created_at, "package": {"client_profile": {"title": pkg.client_profile.title, "pain_points": pkg.client_profile.pain_points, "motivations": pkg.client_profile.motivations, "objections": pkg.client_profile.objections, "best_channels": pkg.client_profile.best_channels, "message_tone": pkg.client_profile.message_tone, "avg_deal_size": pkg.client_profile.avg_deal_size, "buying_cycle": pkg.client_profile.buying_cycle}, "market_map": {"market_size": pkg.market_map.market_size, "growth_trend": pkg.market_map.growth_trend, "opportunities": pkg.market_map.opportunities, "our_position": pkg.market_map.our_position}, "proposal": {"subject": pkg.collaboration_proposal.subject, "full_text": pkg.collaboration_proposal.full_text}, "sales_script": {"opener": pkg.sales_script.opener, "questions": pkg.sales_script.questions, "closer": pkg.sales_script.closer}, "landing_page": {"headline": pkg.landing_page.headline, "benefits": pkg.landing_page.benefits, "cta": pkg.landing_page.cta}, "portfolio": {"title": pkg.portfolio.title, "highlights": pkg.portfolio.highlights, "cta": pkg.portfolio.cta}}})
    except Exception as e:
        log.error(f"[Research] package error: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500
