import logging
import os
from flask import Flask, send_from_directory
from flask_cors import CORS
from config.settings import PORT, DEBUG
from api.routes.whatsapp import whatsapp_bp

log = logging.getLogger(__name__)


def _seed_agents_to_db() -> None:
    """
    Seed the agent DB table from the in-memory registry — idempotent.
    Runs only when the agents table is empty; skipped on subsequent startups.
    """
    from services.storage.repositories.agent_repo import AgentRepository
    repo = AgentRepository()
    if repo.get_active():          # already seeded
        return
    from agents.base.agent_registry import AgentRegistry
    reg = AgentRegistry()
    reg.bootstrap()
    for agent in reg.list_agents():
        try:
            repo.create(
                name=agent.name,
                role=getattr(agent, "name", agent.agent_id),
                department=agent.department,
                capabilities=[],
                model_preference="claude-haiku-4-5",
                risk_tolerance=2,
                system_prompt="",
            )
            log.info(f"[App] seeded agent '{agent.name}' ({agent.department})")
        except Exception as exc:
            log.warning(f"[App] could not seed agent '{agent.agent_id}': {exc}")
    log.info(f"[App] agent seeding complete — {reg.count()} agents")


def create_app() -> Flask:
    app = Flask(__name__, static_folder=None)
    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-secret")
    app.config["JSON_AS_ASCII"] = False
    CORS(app, resources={r"/api/*": {
        "origins": "*",
        "allow_headers": ["Content-Type", "X-API-Key"],
        "methods": ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    }})
    from services.storage.db import create_all_tables
    create_all_tables()
    from events.event_dispatcher import bootstrap
    bootstrap()
    from api.routes.commands import bp as commands_bp
    from api.routes.actions import bp as actions_bp
    from api.routes.leads import bp as leads_bp
    from api.routes.agents import bp as agents_bp
    from api.routes.tasks import bp as tasks_bp
    from api.routes.approvals import bp as approvals_bp
    from api.routes.reports import bp as reports_bp
    from api.routes.system import bp as system_bp
    from api.routes.goals import bp as goals_bp
    from api.routes.dashboard import bp as dashboard_bp
    from api.routes.learning import bp as learning_bp
    from api.routes.outreach import bp as outreach_bp
    from api.routes.research  import bp as research_bp
    from api.routes.delivery  import bp as delivery_bp
    from api.routes.analytics import bp as analytics_bp
    from api.routes.crm      import bp as crm_bp
    from api.routes.webhooks import bp as webhooks_bp
    from api.routes.briefing import bp as briefing_bp

    app.register_blueprint(whatsapp_bp, url_prefix="/api/whatsapp")
    for blueprint in [commands_bp, leads_bp, agents_bp, tasks_bp,
                      approvals_bp, reports_bp, system_bp, actions_bp,
                      goals_bp]:
        app.register_blueprint(blueprint, url_prefix="/api")

    app.register_blueprint(research_bp,  url_prefix='/api/research')
    app.register_blueprint(outreach_bp,  url_prefix='/api')
    app.register_blueprint(learning_bp,  url_prefix='/api/learning')
    app.register_blueprint(dashboard_bp, url_prefix='/api')
    app.register_blueprint(delivery_bp,  url_prefix='/api')
    app.register_blueprint(analytics_bp, url_prefix='/api')
    app.register_blueprint(crm_bp,      url_prefix='/api')
    app.register_blueprint(webhooks_bp, url_prefix='/api')
    app.register_blueprint(briefing_bp, url_prefix='/api')

    from api.routes.admin import bp as admin_bp
    app.register_blueprint(admin_bp, url_prefix='/api')

    from api.routes.revenue_queue import bp as revenue_queue_bp
    app.register_blueprint(revenue_queue_bp, url_prefix='/api')

    from api.routes.claude_dispatch import bp as claude_dispatch_bp
    app.register_blueprint(claude_dispatch_bp, url_prefix='/api')

    from api.routes.gpt_connector import bp as gpt_connector_bp
    app.register_blueprint(gpt_connector_bp, url_prefix='/api')

    from api.routes.mcp import bp as mcp_bp
    app.register_blueprint(mcp_bp, url_prefix='/api')

    from api.routes.openclaw import bp as openclaw_bp
    app.register_blueprint(openclaw_bp, url_prefix='/api')

    from api.routes.telegram import bp as telegram_bp
    app.register_blueprint(telegram_bp, url_prefix='/api')

    from api.routes.seo import bp as seo_bp
    app.register_blueprint(seo_bp, url_prefix='/api')

    from api.routes.lead_ops import bp as lead_ops_bp
    app.register_blueprint(lead_ops_bp, url_prefix='/api')

    from api.routes.intake import bp as intake_bp
    app.register_blueprint(intake_bp, url_prefix='/api')

    # Auth key — OS_API_KEY only (Batch 7: API_KEY fallback removed)
    _active_key = os.getenv("OS_API_KEY", "")
    print(f"Auth: OS_API_KEY Check: {_active_key[:3] if _active_key else 'MISSING'}...")
    log.info(f"[App] auth key loaded: {'yes' if _active_key else 'MISSING — all API calls will be rejected'}")

    ui_root = os.path.join(os.path.dirname(os.path.dirname(__file__)), "ui")

    @app.route("/")
    def serve_index():
        resp = send_from_directory(ui_root, "index.html")
        resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        resp.headers["Pragma"]  = "no-cache"
        resp.headers["Expires"] = "0"
        return resp

    @app.route("/ui/<path:path>")
    def serve_ui(path):
        resp = send_from_directory(ui_root, path)
        resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        resp.headers["Pragma"]  = "no-cache"
        resp.headers["Expires"] = "0"
        return resp

    @app.route("/api/health")
    def health():
        return {"status": "ok"}, 200

    log.info("[App] AshbalOS API ready")

    # Seed agent registry into DB (idempotent — runs only if DB agents table is empty)
    try:
        _seed_agents_to_db()
    except Exception as e:
        log.warning(f"[App] agent seeding failed (non-fatal): {e}")

    # Start autonomous revenue scheduler
    try:
        from scheduler.revenue_scheduler import start as start_scheduler
        start_scheduler()
    except Exception as e:
        log.warning(f"[App] scheduler failed to start: {e}")

    return app

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    app = create_app()
    app.run(host="0.0.0.0", port=PORT, debug=DEBUG)
