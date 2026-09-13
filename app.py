"""Flask application factory and shared extensions.

Creates the app from environment-driven config, registers blueprints,
security features, structured logging and error handlers.
"""
from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from flask import Flask, jsonify, render_template, request

from config import get_config

logger = logging.getLogger("app")


def _configure_logging(app: Flask) -> None:
    fmt = logging.Formatter(
        "%(asctime)s %(levelname)s %(name)s: %(message)s")
    root = logging.getLogger()
    if not root.handlers:
        stream = logging.StreamHandler()
        stream.setFormatter(fmt)
        root.addHandler(stream)
        root.setLevel(logging.DEBUG if app.debug else logging.INFO)

    log_dir = Path(__file__).resolve().parent / "logs"
    if not app.config["TESTING"]:
        try:
            log_dir.mkdir(exist_ok=True)
            handler = RotatingFileHandler(
                log_dir / "attendance.log", maxBytes=1_000_000,
                backupCount=3, encoding="utf-8")
            handler.setFormatter(fmt)
            app.logger.addHandler(handler)
        except OSError:
            app.logger.warning("File logging disabled (no write access).")


def _register_blueprints(app: Flask) -> None:
    from routes import (
        admin, auth, dashboard, notifications, reports, student, teacher,
    )

    app.register_blueprint(auth.bp)
    app.register_blueprint(dashboard.bp)
    app.register_blueprint(admin.bp)
    app.register_blueprint(teacher.bp)
    app.register_blueprint(student.bp)
    app.register_blueprint(reports.bp)
    app.register_blueprint(notifications.bp)


def _register_error_handlers(app: Flask) -> None:
    def render_error(status):
        if request.path.startswith("/api") or request.path == "/health" \
                or request.accept_mimetypes.best == "application/json":
            return jsonify({"error": True, "status": status}), status
        return render_template("errors/error.html",
                               status=status,
                               message=render_template(
                                   f"errors/{status}.html").strip()), status

    for status in (400, 401, 403, 404, 405, 429, 500):
        app.register_error_handler(
            status, lambda e, s=status: render_error(s))

    @app.errorhandler(Exception)
    def unhandled(exc):
        logger.exception("Unhandled error on %s", request.path)
        return render_error(500)


def _init_security(app: Flask) -> None:
    from security.core import init_security
    init_security(app)


def create_app(config_name: str | None = None) -> Flask:
    cfg = get_config(config_name)
    app = Flask(__name__)
    app.config.from_object(cfg)

    _configure_logging(app)

    # CSRF is enforced in security/core.py via a before_request hook so it
    # runs before views that rotate the session (e.g. login).
    from security import core as security_core

    @app.after_request
    def apply_security(response):
        response.headers.setdefault(
            "X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault(
            "Referrer-Policy", "same-origin")
        return response

    security_core.init_security(app)
    _register_blueprints(app)
    _register_error_handlers(app)

    @app.teardown_appcontext
    def close_db(exc):
        # Connections are per-request scoped by explicit open/close in
        # routes; nothing pooled leaks here.
        return None

    return app


# Module-level app for `flask --app app run` compatibility.
app = create_app()


if __name__ == "__main__":
    import os

    cfg = get_config()()
    cfg.validate()
    app.run(
        host=os.getenv("FLASK_HOST", "127.0.0.1"),
        port=int(os.getenv("FLASK_PORT", "5000")),
        debug=app.config.get("DEBUG", False),
    )
