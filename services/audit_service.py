"""Audit trail helpers: every sensitive action is recorded here."""
from __future__ import annotations

from flask import request, session


def log_action(
    db,
    user_id: int | None,
    action: str,
    entity_type: str | None = None,
    entity_id: int | None = None,
    description: str | None = None,
) -> None:
    """Persist an audit record. Never raises to the caller."""
    try:
        ip = None
        try:
            ip = (request.headers.get("X-Forwarded-For", "") or
                  request.remote_addr or "")[:45] or None
        except RuntimeError:
            pass  # outside request context (scripts)
        db.execute(
            """
            INSERT INTO audit_logs (user_id, action, entity_type, entity_id,
                                    description, ip_address)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (user_id, action, entity_type, entity_id, description, ip),
        )
    except Exception:
        # Auditing must never break the main flow.
        pass


def log_session_action(db, action: str, **kwargs) -> None:
    """Audit log using the current session user (0 for anonymous)."""
    user_id = session.get("user_id") or 0
    log_action(db, user_id, action, **kwargs)


def list_audit(db, user_id=None, action=None, date=None, entity_type=None,
               page=1, per_page=20):
    """Filtered, paginated audit history for the admin view."""
    where, params = [], []
    if user_id:
        where.append("a.user_id = %s")
        params.append(user_id)
    if action:
        where.append("a.action LIKE %s")
        params.append(f"%{action}%")
    if date:
        where.append("DATE(a.created_at) = %s")
        params.append(date)
    if entity_type:
        where.append("a.entity_type = %s")
        params.append(entity_type)
    where_sql = ("WHERE " + " AND ".join(where)) if where else ""

    total = db.query_value(
        f"SELECT COUNT(*) FROM audit_logs a {where_sql}", params
    ) or 0
    rows = db.query(
        f"""
        SELECT a.*, u.username
        FROM audit_logs a
        LEFT JOIN users u ON u.user_id = a.user_id
        {where_sql}
        ORDER BY a.created_at DESC
        LIMIT %s OFFSET %s
        """,
        params + [per_page, (page - 1) * per_page],
    )
    return rows, total, (total + per_page - 1) // per_page
