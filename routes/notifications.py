"""Notifications: list, unread count, mark-as-read endpoints."""
from __future__ import annotations

from flask import Blueprint, jsonify, redirect, render_template, session, url_for

from database.db import get_db
from security.core import current_user_id, login_required
from services import notification_service

bp = Blueprint("notifications", __name__)


@bp.route("/notifications")
@login_required
def list_notifications():
    db = get_db()
    try:
        rows = notification_service.list_for_user(db, current_user_id())
        return render_template("notifications/list.html", rows=rows)
    finally:
        db.close()


@bp.route("/notifications/unread_count")
@login_required
def unread_count():
    db = get_db()
    try:
        return jsonify({"count": notification_service.unread_count(
            db, current_user_id())})
    finally:
        db.close()


@bp.route("/notifications/<int:notification_id>/read", methods=["POST"])
@login_required
def mark_read(notification_id):
    db = get_db()
    try:
        notification_service.mark_read(db, current_user_id(), notification_id)
        db.commit()
    finally:
        db.close()
    return redirect(url_for("notifications.list_notifications"))


@bp.route("/notifications/read_all", methods=["POST"])
@login_required
def mark_all_read():
    db = get_db()
    try:
        notification_service.mark_all_read(db, current_user_id())
        db.commit()
    finally:
        db.close()
    return redirect(url_for("notifications.list_notifications"))
