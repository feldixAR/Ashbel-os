import logging
import os
from flask import Flask, send_from_directory
from flask_cors import CORS
from config.settings import PORT, DEBUG
from api.routes.whatsapp import whatsapp_bp

log = logging.getLogger(__name__)

def create_app() -> Flask:
    app = Flask(__name__, static_folder=None)
    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-secret")
    app.config["JSON_AS_ASCII"] = False
    CORS(app)
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
    from api.routes.research import bp as research_bp
    app.register_blueprint(whatsapp_bp, url_prefix="/api/whatsapp")
    for blueprint in [commands_bp, leads_bp, agents_bp, tasks_bp,
                      approvals_bp, reports_bp, system_bp, actions_bp,
                      goals_bp, research_bp]:
        app.register_blueprint(blueprint, url_prefix="/api")
app.register_blueprint(research_bp, url_prefix='/api/research')
app.register_blueprint(outreach_bp, url_prefix='/api/outreach')
app.register_blueprint(learning_bp, url_prefix='/api/learning')
app.register_blueprint(dashboard_bp, url_prefix='/api')
    ui_root = os.path.join(os.path.dirname(os.path.dirname(__file__)), "ui")
    @app.route("/")
    def serve_index():
        return send_from_directory(ui_root, "index.html")
    @app.route("/ui/<path:path>")
    def serve_ui(path):
        return send_from_directory(ui_root, path)

    @app.route("/api/health")
    def health():
        return {"status": "ok"}, 200
    log.info("[App] AshbalOS API ready")
    return app

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    app = create_app()
    app.run(host="0.0.0.0", port=PORT, debug=DEBUG)
