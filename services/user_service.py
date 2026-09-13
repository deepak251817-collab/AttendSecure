"""User, teacher and student account management (admin side)."""
from __future__ import annotations

import os
import re

from werkzeug.security import check_password_hash, generate_password_hash

ROLES = ("admin", "teacher", "student")
STATUS_VALUES = ("present", "absent", "leave")

_USERNAME_RE = re.compile(r"^[A-Za-z0-9_.-]{3,50}$")


# ---------------------------------------------------------------------------
# Password helpers
# ---------------------------------------------------------------------------

def hash_password(password: str) -> str:
    """Hash with the configured method (override via PASSWORD_HASH_METHOD)."""
    try:
        from flask import current_app

        method = current_app.config.get("PASSWORD_HASH_METHOD", "pbkdf2:sha256")
    except RuntimeError:  # outside app context (scripts, seeders)
        method = os.getenv("PASSWORD_HASH_METHOD", "pbkdf2:sha256")
    return generate_password_hash(password, method=method)


def verify_password(pwhash: str, password: str) -> bool:
    try:
        return check_password_hash(pwhash, password)
    except (ValueError, TypeError):
        return False


def validate_password_strength(password: str) -> str | None:
    """Return an error message, or None when acceptable."""
    if not password or len(password) < 6:
        return "Password must be at least 6 characters long."
    return None


def validate_username(username: str) -> str | None:
    if not username or not _USERNAME_RE.match(username):
        return ("Username must be 3-50 characters; letters, numbers, "
                "dot, dash and underscore only.")
    return None


# ---------------------------------------------------------------------------
# Account creation (admin + bulk import)
# ---------------------------------------------------------------------------

def create_user(db, username, role, password, full_name=None, email=None,
                class_id=None, section_id=None, register_number=None,
                department=None, subject_ids=None):
    """Create user + linked teacher/student rows inside one transaction.

    Raises ValueError with a friendly message on invalid input.
    """
    username = (username or "").strip()
    role = (role or "").strip().lower()

    if err := validate_username(username):
        raise ValueError(err)
    if role not in ROLES:
        raise ValueError("Invalid role.")
    if err := validate_password_strength(password or ""):
        raise ValueError(err)

    if db.query_one("SELECT 1 FROM users WHERE username = %s", (username,)):
        raise ValueError("Username already exists.")

    user_id = db.execute(
        """
        INSERT INTO users (username, email, password_hash, full_name, role)
        VALUES (%s, %s, %s, %s, %s)
        """,
        (username, email or None, hash_password(password), full_name or None, role),
    )

    if role == "teacher":
        teacher_id = db.execute(
            "INSERT INTO teachers (user_id, department) VALUES (%s, %s)",
            (user_id, department or None),
        )
        for sid in subject_ids or []:
            db.execute(
                "INSERT IGNORE INTO teacher_subjects (teacher_id, subject_id) "
                "VALUES (%s, %s)",
                (teacher_id, sid),
            )
    elif role == "student":
        db.execute(
            """
            INSERT INTO students (user_id, register_number, class_id, section_id)
            VALUES (%s, %s, %s, %s)
            """,
            (user_id, register_number or None, class_id, section_id),
        )

    return user_id


def update_user(db, user_id, username, role, password=None, full_name=None,
                class_id=None, section_id=None, register_number=None,
                department=None, subject_ids=None):
    """Update an existing account (password optional)."""
    username = (username or "").strip()
    if err := validate_username(username):
        raise ValueError(err)
    if role not in ROLES:
        raise ValueError("Invalid role.")

    exists = db.query_one(
        "SELECT user_id FROM users WHERE username = %s AND user_id <> %s",
        (username, user_id),
    )
    if exists:
        raise ValueError("Username already exists.")

    if password:
        if err := validate_password_strength(password):
            raise ValueError(err)
        db.execute(
            "UPDATE users SET username=%s, role=%s, full_name=%s, password_hash=%s "
            "WHERE user_id=%s",
            (username, role, full_name or None, hash_password(password), user_id),
        )
    else:
        db.execute(
            "UPDATE users SET username=%s, role=%s, full_name=%s WHERE user_id=%s",
            (username, role, full_name or None, user_id),
        )

    if role == "teacher":
        teacher = db.query_one(
            "SELECT teacher_id FROM teachers WHERE user_id=%s", (user_id,)
        )
        teacher_id = teacher["teacher_id"] if teacher else db.execute(
            "INSERT INTO teachers (user_id, department) VALUES (%s, %s)",
            (user_id, department or None),
        )
        db.execute("DELETE FROM teacher_subjects WHERE teacher_id=%s", (teacher_id,))
        for sid in subject_ids or []:
            db.execute(
                "INSERT IGNORE INTO teacher_subjects (teacher_id, subject_id) "
                "VALUES (%s, %s)",
                (teacher_id, sid),
            )
    elif role == "student":
        student = db.query_one(
            "SELECT student_id FROM students WHERE user_id=%s", (user_id,)
        )
        if student:
            db.execute(
                "UPDATE students SET register_number=%s, class_id=%s, section_id=%s "
                "WHERE student_id=%s",
                (register_number or None, class_id, section_id, student["student_id"]),
            )
        else:
            db.execute(
                "INSERT INTO students (user_id, register_number, class_id, section_id) "
                "VALUES (%s, %s, %s, %s)",
                (user_id, register_number or None, class_id, section_id),
            )


def change_own_password(db, user_id, current_password, new_password):
    """Self-service password change; verifies the current password first."""
    row = db.query_one(
        "SELECT password_hash FROM users WHERE user_id=%s", (user_id,)
    )
    if not row or not verify_password(row["password_hash"], current_password or ""):
        raise ValueError("Current password is incorrect.")
    if err := validate_password_strength(new_password or ""):
        raise ValueError(err)
    db.execute(
        "UPDATE users SET password_hash=%s WHERE user_id=%s",
        (hash_password(new_password), user_id),
    )


# ---------------------------------------------------------------------------
# Queries used by routes
# ---------------------------------------------------------------------------

def get_user_with_profile(db, user_id):
    return db.query_one(
        """
        SELECT u.*, s.register_number, s.class_id AS student_class_id,
               s.section_id AS student_section_id, t.department
        FROM users u
        LEFT JOIN students s ON s.user_id = u.user_id
        LEFT JOIN teachers t ON t.user_id = u.user_id
        WHERE u.user_id = %s
        """,
        (user_id,),
    )


def list_users(db, search=None, role=None, page=1, per_page=15):
    where, params = [], []
    if search:
        where.append("(u.username LIKE %s OR u.full_name LIKE %s "
                     "OR s.register_number LIKE %s)")
        params += [f"%{search}%", f"%{search}%", f"%{search}%"]
    if role in ROLES:
        where.append("u.role = %s")
        params.append(role)
    where_sql = ("WHERE " + " AND ".join(where)) if where else ""

    total = db.query_value(
        f"""
        SELECT COUNT(*) FROM users u
        LEFT JOIN students s ON s.user_id = u.user_id
        {where_sql}
        """,
        params,
    ) or 0
    rows = db.query(
        f"""
        SELECT u.user_id, u.username, u.full_name, u.role, u.is_active,
               s.register_number, c.name AS class_name, sec.name AS section_name
        FROM users u
        LEFT JOIN students s ON s.user_id = u.user_id
        LEFT JOIN classes c ON c.class_id = s.class_id
        LEFT JOIN sections sec ON sec.section_id = s.section_id
        {where_sql}
        ORDER BY FIELD(u.role, 'admin', 'teacher', 'student'), u.username
        LIMIT %s OFFSET %s
        """,
        params + [per_page, (page - 1) * per_page],
    )
    return rows, total, (total + per_page - 1) // per_page


def authenticate(db, username, password):
    """Return the user row on success, else None. Auditing is done by caller."""
    row = db.query_one(
        "SELECT user_id, username, password_hash, role, is_active "
        "FROM users WHERE username = %s",
        ((username or "").strip(),),
    )
    if row and row["is_active"] and verify_password(row["password_hash"], password or ""):
        return row
    return None
