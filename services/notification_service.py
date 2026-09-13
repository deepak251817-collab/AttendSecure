"""In-app notification helpers."""
from __future__ import annotations

TYPES = ("info", "leave", "attendance", "warning", "session")


def notify(db, user_id: int, title: str, message: str = "",
           ntype: str = "info") -> int | None:
    """Insert a notification. Best-effort: never breaks the caller flow."""
    if ntype not in TYPES:
        ntype = "info"
    try:
        return db.execute(
            """
            INSERT INTO notifications (user_id, title, message, type)
            VALUES (%s, %s, %s, %s)
            """,
            (user_id, title[:150], message, ntype),
        )
    except Exception:
        return None


def list_for_user(db, user_id: int, limit: int = 30):
    return db.query(
        """
        SELECT notification_id, title, message, type, is_read, created_at
        FROM notifications
        WHERE user_id = %s
        ORDER BY created_at DESC
        LIMIT %s
        """,
        (user_id, limit),
    )


def unread_count(db, user_id: int) -> int:
    return db.query_value(
        "SELECT COUNT(*) FROM notifications WHERE user_id=%s AND is_read=0",
        (user_id,),
    ) or 0


def mark_read(db, user_id: int, notification_id: int) -> bool:
    """Mark one notification read (only if it belongs to the user)."""
    cur = db.execute(
        "UPDATE notifications SET is_read=1 "
        "WHERE notification_id=%s AND user_id=%s AND is_read=0",
        (notification_id, user_id),
    )
    return cur is not None


def mark_all_read(db, user_id: int) -> None:
    db.execute(
        "UPDATE notifications SET is_read=1 WHERE user_id=%s AND is_read=0",
        (user_id,),
    )
