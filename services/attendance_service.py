"""Attendance marking, querying, analytics and edit history."""
from __future__ import annotations

from datetime import date as date_cls

from services.user_service import STATUS_VALUES


def normalize_status(value: str) -> str | None:
    value = (value or "").strip().lower()
    return value if value in STATUS_VALUES else None


def get_teacher_id(db, user_id: int) -> int | None:
    row = db.query_one(
        "SELECT teacher_id FROM teachers WHERE user_id = %s", (user_id,)
    )
    return row["teacher_id"] if row else None


def get_student_id(db, user_id: int) -> int | None:
    row = db.query_one(
        "SELECT student_id FROM students WHERE user_id = %s", (user_id,)
    )
    return row["student_id"] if row else None


def teacher_subjects(db, teacher_id: int) -> list[dict]:
    return db.query(
        """
        SELECT s.subject_id, s.code, s.name
        FROM teacher_subjects ts
        JOIN subjects s ON s.subject_id = ts.subject_id
        WHERE ts.teacher_id = %s
        ORDER BY s.name
        """,
        (teacher_id,),
    )


def teacher_is_assigned(db, teacher_id: int, subject_id: int) -> bool:
    return bool(db.query_one(
        "SELECT 1 FROM teacher_subjects WHERE teacher_id=%s AND subject_id=%s",
        (teacher_id, subject_id),
    ))


def class_sections(db) -> list[dict]:
    """All class/section pairs with display labels."""
    return db.query(
        """
        SELECT sec.section_id, sec.name AS section_name,
               c.class_id, c.name AS class_name,
               CONCAT(c.name, ' - ', sec.name) AS label
        FROM sections sec
        JOIN classes c ON c.class_id = sec.class_id
        ORDER BY c.name, sec.name
        """
    )


def students_of_section(db, section_id: int) -> list[dict]:
    return db.query(
        """
        SELECT s.student_id, u.user_id, u.username, u.full_name,
               s.register_number
        FROM students s
        JOIN users u ON u.user_id = s.user_id
        WHERE s.section_id = %s AND u.is_active = 1
        ORDER BY COALESCE(u.full_name, u.username)
        """,
        (section_id,),
    )


def mark_attendance(db, *, teacher_id, subject_id, class_id, section_id,
                    attendance_date, period, statuses: dict[int, str]) -> int:
    """Upsert one attendance row per student. Returns rows written.

    `statuses` maps student_id -> 'present'|'absent'|'leave'.
    Uses INSERT..ON DUPLICATE KEY UPDATE backed by the DB unique key
    (student_id, subject_id, attendance_date, period).
    """
    marked_by_user = db.query_value(
        "SELECT user_id FROM teachers WHERE teacher_id=%s", (teacher_id,)
    )
    rows = []
    for student_id, status in statuses.items():
        if normalize_status(status) is None:
            continue
        rows.append((
            int(student_id), subject_id, teacher_id, class_id,
            attendance_date, int(period), status, marked_by_user,
        ))
    if not rows:
        return 0
    db.executemany(
        """
        INSERT INTO attendance
            (student_id, subject_id, teacher_id, class_id,
             attendance_date, period, status, marked_by)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            status = VALUES(status),
            teacher_id = VALUES(teacher_id),
            class_id = VALUES(class_id),
            marked_by = VALUES(marked_by)
        """,
        rows,
    )
    return len(rows)


def record_edit(db, attendance_id, old_status, new_status, changed_by_user,
                reason=None):
    db.execute(
        """
        INSERT INTO attendance_edits
            (attendance_id, old_status, new_status, changed_by, reason)
        VALUES (%s, %s, %s, %s, %s)
        """,
        (attendance_id, old_status, new_status, changed_by_user, reason or None),
    )


def attendance_record_for_teacher(db, attendance_id: int, teacher_id: int):
    """Fetch an attendance row, but only when the teacher owns its subject."""
    return db.query_one(
        """
        SELECT a.*, u.username, s.name AS subject_name
        FROM attendance a
        JOIN students st ON st.student_id = a.student_id
        JOIN users u ON u.user_id = st.user_id
        JOIN subjects s ON s.subject_id = a.subject_id
        JOIN teacher_subjects ts ON ts.subject_id = a.subject_id
            AND ts.teacher_id = %s
        WHERE a.attendance_id = %s
        """,
        (teacher_id, attendance_id),
    )


def summary_by_subject(db, student_id: int) -> list[dict]:
    rows = db.query(
        """
        SELECT s.subject_id, s.name AS subject_name,
               COUNT(*) AS total,
               SUM(a.status = 'present') AS present,
               SUM(a.status = 'absent') AS absent,
               SUM(a.status = 'leave') AS `leave`,
               ROUND(100 * SUM(a.status IN ('present', 'leave')) / COUNT(*), 2)
                   AS percentage
        FROM attendance a
        JOIN subjects s ON s.subject_id = a.subject_id
        WHERE a.student_id = %s
        GROUP BY s.subject_id, s.name
        ORDER BY s.name
        """,
        (student_id,),
    )
    for r in rows:
        r["percentage"] = float(r["percentage"] or 0)
    return rows


def overall_stats(db, student_id: int) -> dict:
    row = db.query_one(
        """
        SELECT COUNT(*) AS total,
               COALESCE(SUM(a.status = 'present'), 0) AS present,
               COALESCE(SUM(a.status = 'absent'), 0) AS absent,
               COALESCE(SUM(a.status = 'leave'), 0) AS `leave`
        FROM attendance a
        WHERE a.student_id = %s
        """,
        (student_id,),
    ) or {"total": 0, "present": 0, "absent": 0, "leave": 0}
    total = int(row["total"] or 0)
    attended = int(row["present"] or 0) + int(row["leave"] or 0)
    row["percentage"] = round(100 * attended / total, 2) if total else 0.0
    return row


def history(db, student_id: int, limit: int = 100, offset: int = 0,
            subject_id=None, status=None, start_date=None, end_date=None):
    where = ["a.student_id = %s"]
    params: list = [student_id]
    if subject_id:
        where.append("a.subject_id = %s")
        params.append(subject_id)
    if status in STATUS_VALUES:
        where.append("a.status = %s")
        params.append(status)
    if start_date:
        where.append("a.attendance_date >= %s")
        params.append(start_date)
    if end_date:
        where.append("a.attendance_date <= %s")
        params.append(end_date)
    where_sql = "WHERE " + " AND ".join(where)
    rows = db.query(
        f"""
        SELECT a.attendance_id, a.attendance_date, a.period, a.status,
               s.name AS subject_name
        FROM attendance a
        JOIN subjects s ON s.subject_id = a.subject_id
        {where_sql}
        ORDER BY a.attendance_date DESC, a.period DESC
        LIMIT %s OFFSET %s
        """,
        params + [limit, offset],
    )
    total = db.query_value(
        f"SELECT COUNT(*) FROM attendance a {where_sql}", params
    ) or 0
    return rows, total


def teacher_history(db, teacher_id: int, subject_id=None, section_id=None,
                    start_date=None, end_date=None, status=None,
                    page: int = 1, per_page: int = 25):
    where = ["ts.teacher_id = %s"]
    params: list = [teacher_id]
    if subject_id:
        where.append("a.subject_id = %s")
        params.append(subject_id)
    if section_id:
        where.append("s.section_id = %s")
        params.append(section_id)
    if status in STATUS_VALUES:
        where.append("a.status = %s")
        params.append(status)
    if start_date:
        where.append("a.attendance_date >= %s")
        params.append(start_date)
    if end_date:
        where.append("a.attendance_date <= %s")
        params.append(end_date)
    where_sql = " AND ".join(where)

    base = f"""
        FROM attendance a
        JOIN students st ON st.student_id = a.student_id
        JOIN users u ON u.user_id = st.user_id
        JOIN subjects sub ON sub.subject_id = a.subject_id
        JOIN teacher_subjects ts ON ts.subject_id = a.subject_id
        LEFT JOIN sections sec ON sec.section_id = st.section_id
        LEFT JOIN classes c ON c.class_id = sec.class_id
        WHERE {where_sql}
    """
    total = db.query_value(f"SELECT COUNT(*) {base}", params) or 0
    rows = db.query(
        f"""
        SELECT a.attendance_id, a.attendance_date, a.period, a.status,
               u.username, COALESCE(u.full_name, u.username) AS display_name,
               sub.name AS subject_name, a.subject_id,
               c.name AS class_name, sec.name AS section_name
        {base}
        ORDER BY a.attendance_date DESC, a.period DESC, u.username
        LIMIT %s OFFSET %s
        """,
        params + [per_page, (page - 1) * per_page],
    )
    return rows, total, (total + per_page - 1) // per_page


def section_summary(db, section_id: int, subject_id: int | None = None):
    """Per-student attendance summary for a section (optionally one subject)."""
    subject_filter = ""
    params: list = [section_id]
    if subject_id:
        subject_filter = "AND a.subject_id = %s"
        params.append(subject_id)
    return db.query(
        f"""
        SELECT u.user_id, u.username, COALESCE(u.full_name, u.username) AS display_name,
               s.register_number,
               COUNT(a.attendance_id) AS total,
               COALESCE(SUM(a.status = 'present'), 0) AS present,
               COALESCE(SUM(a.status = 'absent'), 0) AS absent,
               COALESCE(SUM(a.status = 'leave'), 0) AS `leave`,
               CASE WHEN COUNT(a.attendance_id) = 0 THEN NULL
                    ELSE ROUND(100 * SUM(a.status IN ('present', 'leave'))
                               / COUNT(a.attendance_id), 2)
               END AS percentage
        FROM students s
        JOIN users u ON u.user_id = s.user_id
        LEFT JOIN attendance a
            ON a.student_id = s.student_id {subject_filter}
        WHERE s.section_id = %s AND u.is_active = 1
        GROUP BY u.user_id, u.username, s.register_number
        ORDER BY u.username
        """,
        params,
    )


def low_attendance(db, threshold: float = 75.0, section_id=None,
                   subject_id=None, limit: int = 100):
    """Students below threshold, with classes needed to reach it."""
    subject_filter = ""
    params: list = []
    if section_id:
        subject_filter += " AND s.section_id = %s"
        params.append(section_id)
    if subject_id:
        subject_filter += " AND a.subject_id = %s"
        params.append(subject_id)
    rows = db.query(
        f"""
        SELECT u.user_id, s.student_id, u.username,
               COALESCE(u.full_name, u.username) AS display_name,
               c.name AS class_name, sec.name AS section_name,
               COUNT(a.attendance_id) AS total,
               COALESCE(SUM(a.status IN ('present', 'leave')), 0) AS attended,
               ROUND(100 * SUM(a.status IN ('present', 'leave'))
                     / COUNT(a.attendance_id), 2) AS percentage,
               sub.name AS subject_name, a.subject_id
        FROM students s
        JOIN users u ON u.user_id = s.user_id
        LEFT JOIN sections sec ON sec.section_id = s.section_id
        LEFT JOIN classes c ON c.class_id = sec.class_id
        JOIN attendance a ON a.student_id = s.student_id {subject_filter}
        LEFT JOIN subjects sub ON sub.subject_id = a.subject_id
        WHERE u.is_active = 1
        GROUP BY s.student_id, u.user_id, u.username, c.name, sec.name, sub.name,
                 a.subject_id
        HAVING percentage < %s
        ORDER BY percentage ASC
        LIMIT %s
        """,
        params + [threshold, limit],
    )
    for r in rows:
        total = int(r["total"] or 0)
        attended = int(r["attended"] or 0)
        # n such that (attended + n) / (total + n) >= threshold
        needed = 0
        if 0 < threshold < 100 and total > 0:
            needed = -(-(threshold / 100 * total - attended) // (1 - threshold / 100))
        r["classes_needed"] = max(int(needed), 0)
    return rows


def today_counts(db, section_id=None, teacher_id=None):
    """Present/absent/leave counts for today (dashboard cards)."""
    where = ["a.attendance_date = CURDATE()"]
    params: list = []
    if section_id:
        where.append("st.section_id = %s")
        params.append(section_id)
    if teacher_id:
        where.append("a.teacher_id = %s")
        params.append(teacher_id)
    row = db.query_one(
        f"""
        SELECT COALESCE(SUM(a.status='present'),0) AS present,
               COALESCE(SUM(a.status='absent'),0) AS absent,
               COALESCE(SUM(a.status='leave'),0) AS `leave`,
               COUNT(*) AS total
        FROM attendance a
        JOIN students st ON st.student_id = a.student_id
        WHERE {' AND '.join(where)}
        """,
        params,
    ) or {}
    return row


def monthly_trend(db, student_id: int):
    rows = db.query(
        """
        SELECT DATE_FORMAT(a.attendance_date, '%%Y-%%m') AS month,
               COUNT(*) AS total,
               SUM(a.status IN ('present','leave')) AS attended,
               ROUND(100 * SUM(a.status IN ('present','leave')) / COUNT(*), 2)
                   AS percentage
        FROM attendance a
        WHERE a.student_id = %s
        GROUP BY month
        ORDER BY month DESC
        LIMIT 12
        """,
        (student_id,),
    )
    for r in rows:
        r["percentage"] = float(r["percentage"] or 0)
    return rows
