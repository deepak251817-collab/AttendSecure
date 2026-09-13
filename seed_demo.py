"""Seed demo data (classes, sections, subjects, users, timetable).

Optional convenience for demonstrations. Run AFTER reset_db.py:

    python seed_demo.py

All demo passwords are printed at the end and are intended for local
demonstration only — never use this on a production database.
"""
from __future__ import annotations

import random
import sys
from datetime import date, timedelta

from config import get_config
from database.db import get_db
from database.db_manager import wait_for_server
from services import academic_service, user_service


def main() -> int:
    cfg = get_config()()
    cfg.validate()
    if not wait_for_server(cfg, timeout=15):
        print("MySQL not reachable.")
        return 1

    db = get_db(cfg)
    demo_passwords = []
    try:
        # Academic structure
        classes = {}
        for class_name in ("CSE", "AIML"):
            try:
                academic_service.create_class(db, class_name)
            except ValueError:
                pass
            classes[class_name] = db.query_value(
                "SELECT class_id FROM classes WHERE name=%s", (class_name,))
        sections = {}
        for class_name in classes:
            for sec in ("A", "B"):
                try:
                    academic_service.create_section(db, classes[class_name], sec)
                except ValueError:
                    pass
                sections[f"{class_name}-{sec}"] = db.query_value(
                    "SELECT section_id FROM sections WHERE class_id=%s AND name=%s",
                    (classes[class_name], sec))

        subjects = {}
        for code, name in (("CS101", "Data Structures"),
                           ("CS102", "Operating Systems"),
                           ("CS103", "Databases")):
            try:
                academic_service.create_subject(db, name, code)
            except ValueError:
                pass
            subjects[code] = db.query_value(
                "SELECT subject_id FROM subjects WHERE code=%s", (code,))

        # Teachers
        teachers = []
        for username, name, dept in (("teacher1", "Priya N", "CSE"),
                                     ("teacher2", "Ravi K", "AIML")):
            if not db.query_one("SELECT 1 FROM users WHERE username=%s",
                                (username,)):
                uid = user_service.create_user(db, username, "teacher",
                                               "teach@123", full_name=name,
                                               department=dept)
                demo_passwords.append((username, "teach@123"))
            else:
                uid = db.query_value("SELECT user_id FROM users WHERE username=%s",
                                     (username,))
            teachers.append(db.query_value(
                "SELECT teacher_id FROM teachers WHERE user_id=%s", (uid,)))

        # Assign subjects: build mapping first, then assign per teacher once
        teacher_subject_map = {tid: [] for tid in teachers}
        for i, (code, sid) in enumerate(subjects.items()):
            teacher_subject_map[teachers[i % len(teachers)]].append(sid)
        for tid, sids in teacher_subject_map.items():
            academic_service.assign_teacher_subjects(db, tid, sids)
        db.commit()

        # Students in each section
        reg = 1
        for key, section_id in sections.items():
            for n in range(1, 6):
                username = f"student_{key.split('-')[0].lower()}{key[-1]}{n:02d}"
                if db.query_one("SELECT 1 FROM users WHERE username=%s",
                                (username,)):
                    continue
                user_service.create_user(
                    db, username, "student", "study@123",
                    full_name=f"Student {key} {n:02d}",
                    class_id=classes[key.split("-")[0]],
                    section_id=section_id,
                    register_number=f"REG{reg:04d}")
                demo_passwords.append((username, "study@123"))
                reg += 1
        db.commit()

        # Timetable (Mon-Fri, periods 1-2, subjects rotated)
        timetable_rows = []
        for key, section_id in sections.items():
            class_id = db.query_value(
                "SELECT class_id FROM sections WHERE section_id=%s", (section_id,))
            for day in range(1, 6):
                for period, (code, sid) in enumerate(list(subjects.items())[:2],
                                                     start=1):
                    teacher_id = teachers[(day + period) % len(teachers)]
                    start = f"0{8 + period}:00:00" if 8 + period < 10 \
                        else f"{8 + period}:00:00"
                    end = f"0{8 + period}:45:00" if 8 + period < 10 \
                        else f"{8 + period}:45:00"
                    timetable_rows.append((class_id, section_id, sid, teacher_id,
                                           day, period, start, end))
        db.executemany(
            """
            INSERT IGNORE INTO timetable
                (class_id, section_id, subject_id, teacher_id, day_of_week,
                 period, start_time, end_time)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            timetable_rows,
        )
        db.commit()

        # Sample attendance for the last 14 days (80% present)
        student_ids = [r["student_id"] for r in db.query("SELECT student_id FROM students")]
        today = date.today()
        attendance_rows = []
        for delta in range(1, 15):
            d = today - timedelta(days=delta)
            if d.weekday() >= 5:
                continue  # skip weekends
            for code, sid in subjects.items():
                for st in student_ids:
                    roll = random.random()
                    status = "present" if roll > 0.2 else "absent"
                    attendance_rows.append(
                        (st, sid, teachers[0], d, 1, status))
        db.executemany(
            """
            INSERT IGNORE INTO attendance
                (student_id, subject_id, teacher_id, attendance_date, period,
                 status)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            attendance_rows,
        )
        db.commit()

        print("\nDemo data ready. Accounts (demo only, change before real use):")
        for username, pwd in demo_passwords[:8]:
            print(f"  {username:<14} password: {pwd}")
        if db.query_value("SELECT COUNT(*) FROM users WHERE username='admin'"):
            print("  admin           password: (set during reset_db.py)")
        print(f"\nStudents: {db.query_value('SELECT COUNT(*) FROM users WHERE role=%s', ('student',))}"
              f" | Attendance rows: {db.query_value('SELECT COUNT(*) FROM attendance')}")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
