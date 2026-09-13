"""Role dispatch: /dashboard sends each role to its own dashboard."""
from __future__ import annotations

from flask import Blueprint, redirect, session, url_for

from security.core import login_required

bp = Blueprint("dashboard", __name__)


@bp.route("/dashboard")
@login_required
def dashboard():
    role = session.get("role")
    if role == "admin":
        return redirect(url_for("admin.dashboard"))
    if role == "teacher":
        return redirect(url_for("teacher.dashboard"))
    if role == "student":
        return redirect(url_for("student.dashboard"))
    return redirect(url_for("auth.login"))
