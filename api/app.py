"""
app.py — Flask application factory.
Creates and configures the Flask app:
    1. Initialises DB (create_all_tables)
    2. Bootstraps event dispatcher + AgentRegistry
    3. Registers all route blueprints under /api
Usage (production):
    gunicorn "api.app:create_app()"
Usage (development):
    python api/app.py
"""
import logging
import os
from flask import Flask, send_from_directory
from flask_cors import CORS
from config.settings import PORT, DEBUG

log = logging.getLogger(__name__)

def create_app() -> Flask:
    app = Flask(__name__, static_folder=None)
    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-secret")
    app.config["JSON_AS_ASCII"] = False

    CORS(app)

    # ── 1. Database ───────────────────────────────────────────────────────────
    from services.storage.db import create_all_tables
    create_all_tables()

    # ── 2. Event dispatcher + AgentRegistry ──────────────────────────────────
    from events.event_dispatcher import bootstrap
    bootstrap()

    # ── 3. Blueprints ─────────────────────────────────────────────────────────
    from api.routes.commands  import bp as commands_bp
    from api.routes.actions   import bp as actions_bp
    from api.routes.leads     import bp as leads_bp
    from api.routes.agents    import bp as agents_bp
    from api.routes.tasks     import bp as tasks_bp
    from api.routes.approvals import bp as approvals_bp
    from api.routes.reports   import bp as reports_bp
    from api.routes.system    import bp as system_bp

    for blueprint in [commands_bp, leads_bp, agents_bp, tasks_bp,
                      approvals_bp, reports_bp, system_bp, actions_bp]:
        app.register_blueprint(blueprint, url_prefix="/api")

    # ── 4. Serve UI static files ──────────────────────────────────────────────
    ui_root = os.path.join(os.path.dirname(os.path.dirname(__file__)), "ui")

    @app.route("/")
    def serve_index():
        return send_from_directory(ui_root, "index.html")

    @app.route("/ui/<path:path>")
    def serve_ui(path):
        return send_from_directory(ui_root, path)

    log.info("[App] AshbalOS API ready")
    return app

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    app = create_app()
    app.run(host="0.0.0.0", port=PORT, debug=DEBUG)
```

---

אחרי שהעתקת ושמרת — פתח `requirements.txt` ובדוק אם יש `flask-cors`. אם לא — הוסף שם:
```
flask-cors
