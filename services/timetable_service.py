"""Timetable management with backend conflict validation."""
from __future__ import annotations

from datetime import time as time_cls

DAYS = {1: "Monday", 2: "Tuesday", 3: "Wednesday", 4: "Thursday",
        5: "Friday", 6: "Saturday", 7: "Sunday"}


def _parse_time(value):
    try:
        h, m = (int(x) for x in str(value).split(":")[:2])
        return time_cls(h, m)
    except (TypeError, ValueError):
        return None


def validate_entry(db, *, class_id, section_id, subject_id, teacher_id,
                   day_of_week, period, start_time, end_time,
                   exclude_id=None):
    """Return a list of conflict messages; empty list means valid."""
    errors: list[str] = []
    start = _parse_time(start_time)
    end = _parse_time(end_time)
    if start is None or end is None:
        errors.append("Start and end times must be in HH:MM format.")
        return errors
    if end <= start:
        errors.append("End time must be after the start time.")
    day = int(day_of_week)
    if not 1 <= day <= 7:
        errors.append("Day of week must be between 1 (Monday) and 7 (Sunday).")
    period = int(period)
    if not 1 <= period <= 12:
        errors.append("Period must be between 1 and 12.")

    # The class/section must not already have a subject in that slot.
    clash = db.query_one(
        """
        SELECT t.timetable_id, s.name AS subject_name
        FROM timetable t JOIN subjects s ON s.subject_id = t.subject_id
        WHERE t.class_id=%s AND t.section_id=%s
          AND t.day_of_week=%s AND t.period=%s
          AND t.timetable_id <> COALESCE(%s, -1)
        """,
        (class_id, section_id, day, period, exclude_id),
    )
    if clash:
        errors.append(
            f"This class already has {clash['subject_name']} in that slot."
        )

    # The teacher must not be in two places at the same time (overlap check).
    busy = db.query_one(
        """
        SELECT t.timetable_id, s.name AS subject_name
        FROM timetable t
        JOIN subjects s ON s.subject_id = t.subject_id
        WHERE t.teacher_id=%s AND t.day_of_week=%s
          AND t.start_time < %s AND t.end_time > %s
          AND t.timetable_id <> COALESCE(%s, -1)
        """,
        (teacher_id, day, end, start, exclude_id),
    )
    if busy:
        errors.append(
            f"The teacher already teaches {busy['subject_name']} in an "
            "overlapping slot."
        )
    return errors


def timetable_for_section(db, section_id: int) -> list[dict]:
    return db.query(
        """
        SELECT t.timetable_id, t.day_of_week, t.period, t.start_time,
               t.end_time, s.name AS subject_name,
               COALESCE(u.full_name, u.username) AS teacher_name
        FROM timetable t
        JOIN subjects s ON s.subject_id = t.subject_id
        JOIN teachers te ON te.teacher_id = t.teacher_id
        JOIN users u ON u.user_id = te.user_id
        WHERE t.section_id = %s
        ORDER BY t.day_of_week, t.period
        """,
        (section_id,),
    )


def timetable_for_teacher(db, teacher_id: int) -> list[dict]:
    return db.query(
        """
        SELECT t.timetable_id, t.day_of_week, t.period, t.start_time,
               t.end_time, s.name AS subject_name,
               c.name AS class_name, sec.name AS section_name
        FROM timetable t
        JOIN subjects s ON s.subject_id = t.subject_id
        JOIN classes c ON c.class_id = t.class_id
        JOIN sections sec ON sec.section_id = t.section_id
        WHERE t.teacher_id = %s
        ORDER BY t.day_of_week, t.period
        """,
        (teacher_id,),
    )


def list_entries(db) -> list[dict]:
    return db.query(
        """
        SELECT t.timetable_id, t.day_of_week, t.period, t.start_time,
               t.end_time, s.name AS subject_name,
               COALESCE(u.full_name, u.username) AS teacher_name,
               c.name AS class_name, sec.name AS section_name
        FROM timetable t
        JOIN subjects s ON s.subject_id = t.subject_id
        JOIN teachers te ON te.teacher_id = t.teacher_id
        JOIN users u ON u.user_id = te.user_id
        JOIN classes c ON c.class_id = t.class_id
        JOIN sections sec ON sec.section_id = t.section_id
        ORDER BY c.name, sec.name, t.day_of_week, t.period
        """
    )
