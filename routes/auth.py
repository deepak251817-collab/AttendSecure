"""Authentication routes: login, logout, health."""
from __future__ import annotations

from flask import (
    Blueprint, current_app, flash, jsonify, redirect, render_template,
    request, session, url_for,
)

from database.db import DatabaseError, get_db
from security.core import (
    login_rate_limited, record_failed_login, reset_login_attempts,
)
from services import audit_service, user_service

bp = Blueprint("auth", __name__)


@bp.route("/")
def home():
    return redirect(url_for("auth.login"))


@bp.route("/health")
def health():
    """Health check used by Docker and local monitoring."""
    try:
        db = get_db()
        ok = db.ping()
        db.close()
        return jsonify({"status": "ok" if ok else "error",
                        "service": "attendance-system"}), 200 if ok else 503
    except DatabaseError:
        return jsonify({"status": "error", "service": "attendance-system"}), 503


@bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        limited, retry = login_rate_limited()
        if limited:
            flash(f"Too many failed attempts. Try again in {retry} seconds.",
                  "error")
            return render_template("login.html"), 429

        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""

        db = None
        try:
            db = get_db()
            user = user_service.authenticate(db, username, password)
            if user:
                session.clear()
                session["user_id"] = user["user_id"]
                session["username"] = user["username"]
                session["role"] = user["role"]
                reset_login_attempts()
                audit_service.log_action(db, user["user_id"], "login",
                                         "user", user["user_id"],
                                         f"{user['username']} logged in")
                db.commit()

                next_url = request.args.get("next")
                if next_url and next_url.startswith("/") \
                        and not next_url.startswith("//"):
                    return redirect(next_url)
                return redirect(url_for("dashboard.dashboard"))
            flash("Invalid username or password.", "error")
            record_failed_login()
            return render_template("login.html"), 401
        except DatabaseError as exc:
            current_app.logger.error("Login DB failure: %s", exc)
            flash("Database is unavailable. Please try again later.", "error")
            return render_template("login.html"), 503
        finally:
            if db is not None:
                db.close()

    return render_template("login.html")


@bp.route("/logout")
def logout():
    user_id = session.get("user_id")
    username = session.get("username")
    session.clear()
    if user_id:
        try:
            db = get_db()
            audit_service.log_action(db, user_id, "logout", "user", user_id,
                                     f"{username} logged out")
            db.commit()
            db.close()
        except DatabaseError:
            pass
    return redirect(url_for("auth.login"))
