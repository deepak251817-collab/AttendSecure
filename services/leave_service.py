"""Leave request workflow: student submits, teacher approves/rejects."""
from __future__ import annotations

from datetime import date as date_cls


def _parse_date(value):
    try:
        return date_cls.fromisoformat(value or "")
    except (TypeError, ValueError):
        return None


def create_request(db, student_id, start_date, end_date, reason,
                   subject_id=None):
    """Create a leave request after validation. Raises ValueError on error."""
    start = _parse_date(start_date)
    end = _parse_date(end_date)
    if not start or not end:
        raise ValueError("Please provide valid start and end dates (YYYY-MM-DD).")
    if end < start:
        raise ValueError("End date cannot be before the start date.")
    if not (reason or "").strip():
        raise ValueError("Please provide a reason for the leave.")

    overlapping = db.query_one(
        """
        SELECT leave_id FROM leave_requests
        WHERE student_id = %s AND status = 'pending'
          AND NOT (end_date < %s OR start_date > %s)
        """,
        (student_id, start, end),
    )
    if overlapping:
        raise ValueError("You already have a pending leave request that "
                         "overlaps these dates.")

    # Route to a teacher who takes classes for this student's section;
    # fall back to any teacher of a subject the student attends.
    teacher = db.query_one(
        """
        SELECT tt.teacher_id
        FROM students s
        JOIN timetable tt ON tt.section_id = s.section_id
        WHERE s.student_id = %s
        ORDER BY RAND() LIMIT 1
        """,
        (student_id,),
    )
    if teacher is None:
        teacher = db.query_one(
            "SELECT teacher_id FROM teacher_subjects ORDER BY RAND() LIMIT 1")
    leave_id = db.execute(
        """
        INSERT INTO leave_requests
            (student_id, teacher_id, subject_id, start_date, end_date, reason,
             status)
        VALUES (%s, %s, %s, %s, %s, %s, 'pending')
        """,
        (student_id, teacher["teacher_id"] if teacher else None,
         subject_id, start, end, reason.strip()),
    )
    return leave_id


def teacher_requests(db, teacher_id: int, status=None):
    """Leave requests visible to a teacher (assigned or same section)."""
    where = """
        WHERE (lr.teacher_id = %s
               OR EXISTS (
                   SELECT 1 FROM leave_requests lr2
                   JOIN students st2 ON st2.student_id = lr2.student_id
                   JOIN timetable tt2 ON tt2.section_id = st2.section_id
                   WHERE lr2.leave_id = lr.leave_id AND tt2.teacher_id = %s
               ))
    """
    params: list = [teacher_id, teacher_id]
    if status in ("pending", "approved", "rejected"):
        where += " AND lr.status = %s"
        params.append(status)
    return db.query(
        f"""
        SELECT lr.*, u.username, COALESCE(u.full_name, u.username) AS student_name,
               s.name AS subject_name
        FROM leave_requests lr
        JOIN students st ON st.student_id = lr.student_id
        JOIN users u ON u.user_id = st.user_id
        LEFT JOIN subjects s ON s.subject_id = lr.subject_id
        {where}
        ORDER BY FIELD(lr.status, 'pending', 'approved', 'rejected'),
                 lr.created_at DESC
        """,
        params,
    )


def student_requests(db, student_id: int):
    return db.query(
        """
        SELECT lr.*, s.name AS subject_name,
               approver.username AS approver_name
        FROM leave_requests lr
        LEFT JOIN subjects s ON s.subject_id = lr.subject_id
        LEFT JOIN teachers t ON t.teacher_id = lr.approved_by
        LEFT JOIN users approver ON approver.user_id = t.user_id
        WHERE lr.student_id = %s
        ORDER BY lr.created_at DESC
        """,
        (student_id,),
    )


def decide(db, leave_id: int, teacher_id: int, decision: str) -> None:
    """Approve/reject a leave request after authorization.

    Raises ValueError when the teacher is not relevant to the request or it
    has already been decided.
    """
    decision = (decision or "").strip().lower()
    if decision not in ("approved", "rejected"):
        raise ValueError("Invalid decision.")

    row = db.query_one(
        "SELECT leave_id, status FROM leave_requests WHERE leave_id=%s",
        (leave_id,),
    )
    if not row:
        raise ValueError("Leave request not found.")
    if row["status"] != "pending":
        raise ValueError("This request has already been decided.")

    # Authorization: assigned reviewer OR teacher of the student's section.
    allowed = bool(db.query_one(
        """
        SELECT 1
        FROM leave_requests lr
        JOIN students st ON st.student_id = lr.student_id
        WHERE lr.leave_id = %s
          AND (lr.teacher_id = %s
               OR EXISTS (SELECT 1 FROM timetable tt
                          WHERE tt.section_id = st.section_id
                            AND tt.teacher_id = %s))
        LIMIT 1
        """,
        (leave_id, teacher_id, teacher_id),
    ))
    if not allowed:
        raise ValueError("You are not authorized to manage this leave request.")

    db.execute(
        """
        UPDATE leave_requests
        SET status = %s, approved_by = %s
        WHERE leave_id = %s
        """,
        (decision, teacher_id, leave_id),
    )
