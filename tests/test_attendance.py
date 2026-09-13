"""Attendance tests: marking, duplicates, authorization, percentages, edits."""
from __future__ import annotations

from datetime import date, timedelta

from database.db import get_db
from services import attendance_service

TODAY = date.today()


def _section_students(db, seed):
    return attendance_service.students_of_section(db, seed["section_id"])


def _load_roster(teacher_client, seed, day=TODAY, period=1):
    return teacher_client.post(
        "/mark_attendance",
        data={"section_id": str(seed["section_id"]),
              "subject_id": str(seed["subject_ids"][0]),
              "attendance_date": day.isoformat(),
              "period": str(period)},
    )


def _submit(teacher_client, seed, statuses: dict[int, str],
            day=TODAY, period=1):
    data = {"section_id": str(seed["section_id"]),
            "subject_id": str(seed["subject_ids"][0]),
            "class_id": str(seed["class_id"]),
            "attendance_date": day.isoformat(),
            "period": str(period)}
    for student_id, status in statuses.items():
        data[f"status_{student_id}"] = status
    return teacher_client.post("/submit_attendance", data=data,
                               follow_redirects=False)


def test_teacher_can_mark_attendance(teacher_client, seed, test_db):
    roster = _load_roster(teacher_client, seed)
    assert roster.status_code == 200
    students = _section_students(get_db(test_db), seed)
    response = _submit(teacher_client, seed,
                       {s["student_id"]: "present" for s in students})
    assert response.status_code == 302
    db = get_db(test_db)
    try:
        count = db.query_value(
            "SELECT COUNT(*) FROM attendance WHERE attendance_date=%s",
            (TODAY,))
        assert count == len(students)
    finally:
        db.close()


def test_duplicate_attendance_rejected_by_unique_constraint(
        teacher_client, seed, test_db):
    students = _section_students(get_db(test_db), seed)
    first = _submit(teacher_client, seed,
                    {s["student_id"]: "present" for s in students})
    assert first.status_code == 302
    # Re-submit with different statuses: upsert must not duplicate rows.
    second = _submit(teacher_client, seed,
                     {s["student_id"]: "absent" for s in students})
    assert second.status_code == 302
    db = get_db(test_db)
    try:
        count = db.query_value(
            "SELECT COUNT(*) FROM attendance WHERE attendance_date=%s",
            (TODAY,))
        assert count == len(students)  # still one row per student
        status = db.query_value(
            "SELECT status FROM attendance WHERE student_id=%s "
            "AND subject_id=%s AND attendance_date=%s AND period=1",
            (students[0]["student_id"], seed["subject_ids"][0], TODAY))
        assert status == "absent"
    finally:
        db.close()


def test_teacher_cannot_mark_unassigned_subject(teacher_client, seed,
                                                test_db):
    db = get_db(test_db)
    try:
        # teacher2 exists but has no subject assignments
        unassigned_subject = db.query_value(
            "SELECT s.subject_id FROM subjects s "
            "LEFT JOIN teacher_subjects ts ON ts.subject_id = s.subject_id "
            "WHERE ts.teacher_id = (SELECT teacher_id FROM teachers t "
            "JOIN users u ON u.user_id=t.user_id WHERE u.username='teacher2') "
            "OR ts.teacher_id IS NULL LIMIT 1")
    finally:
        db.close()
    from tests.conftest import login
    login(teacher_client, "teacher2", "teachpass")
    data = {"section_id": str(seed["section_id"]),
            "subject_id": str(unassigned_subject),
            "class_id": str(seed["class_id"]),
            "attendance_date": TODAY.isoformat(), "period": "1",
            "status_1": "present"}
    response = teacher_client.post("/submit_attendance", data=data,
                                   follow_redirects=True)
    assert b"not assigned" in response.data


def test_student_cannot_submit_attendance(student_client, seed):
    response = student_client.post(
        "/submit_attendance",
        data={"section_id": str(seed["section_id"]),
              "subject_id": str(seed["subject_ids"][0]),
              "attendance_date": TODAY.isoformat(), "period": "1",
              "status_1": "present"},
        follow_redirects=True)
    assert response.status_code == 403


def test_attendance_percentage_calculations(teacher_client, seed, test_db):
    students = _section_students(get_db(test_db), seed)
    s = students[0]
    # Day 1: present, Day 2: absent, Day 3: leave
    for i, status in enumerate(("present", "absent", "leave"), start=1):
        _submit(teacher_client, seed, {s["student_id"]: status},
                day=TODAY + timedelta(days=i))
    db = get_db(test_db)
    try:
        overall = attendance_service.overall_stats(db, s["student_id"])
        assert overall["total"] == 3
        assert overall["present"] == 1
        assert overall["absent"] == 1
        assert overall["leave"] == 1
        # present + leave both count as attended
        assert overall["percentage"] == round(2 / 3 * 100, 2)
        by_subject = attendance_service.summary_by_subject(
            db, s["student_id"])
        assert len(by_subject) == 1
        assert by_subject[0]["total"] == 3
    finally:
        db.close()


def test_edit_attendance_creates_history(teacher_client, seed, test_db):
    students = _section_students(get_db(test_db), seed)
    s = students[0]
    _submit(teacher_client, seed, {s["student_id"]: "present"})
    db = get_db(test_db)
    try:
        att_id = db.query_value(
            "SELECT attendance_id FROM attendance WHERE student_id=%s",
            (s["student_id"],))
        assert att_id
    finally:
        db.close()

    response = teacher_client.post(
        f"/attendance/{att_id}/edit",
        data={"status": "absent", "reason": "Arrived very late"},
        follow_redirects=True)
    assert response.status_code == 200

    db = get_db(test_db)
    try:
        new_status = db.query_value(
            "SELECT status FROM attendance WHERE attendance_id=%s", (att_id,))
        assert new_status == "absent"
        edit = db.query_one(
            "SELECT old_status, new_status, reason FROM attendance_edits "
            "WHERE attendance_id=%s", (att_id,))
        assert edit["old_status"] == "present"
        assert edit["new_status"] == "absent"
        assert edit["reason"] == "Arrived very late"
    finally:
        db.close()


def test_teacher_cannot_edit_other_subjects_attendance(teacher_client,
                                                       seed, test_db):
    db = get_db(test_db)
    try:
        teacher2 = db.query_value(
            "SELECT teacher_id FROM teachers t JOIN users u "
            "ON u.user_id=t.user_id WHERE u.username='teacher2'")
        student_id = db.query_value(
            "SELECT student_id FROM students s JOIN users u "
            "ON u.user_id = s.user_id WHERE u.username='student1'")
        # A subject assigned ONLY to teacher2 (teacher1 must not see it).
        own_subject = db.execute(
            "INSERT INTO subjects (code, name) VALUES ('X999', 'Private Subject')")
        db.execute(
            "INSERT INTO teacher_subjects (teacher_id, subject_id) "
            "VALUES (%s, %s)", (teacher2, own_subject))
        att_id = db.execute(
            "INSERT INTO attendance (student_id, subject_id, teacher_id, "
            "class_id, attendance_date, period, status) "
            "VALUES (%s, %s, %s, %s, %s, 5, 'present')",
            (student_id, own_subject, teacher2,
             seed["class_id"], TODAY))
        db.commit()
        att_id_int = int(att_id)
    finally:
        db.close()
    response = teacher_client.get(f"/attendance/{att_id_int}/edit",
                                  follow_redirects=True)
    assert b"not yours to edit" in response.data


def test_low_attendance_flags_and_classes_needed(teacher_client, seed,
                                                 test_db):
    students = _section_students(get_db(test_db), seed)
    s = students[0]
    # 1 present, 3 absent -> 25%
    _submit(teacher_client, seed, {s["student_id"]: "present"},
            day=TODAY + timedelta(days=1))
    for i in (2, 3, 4):
        _submit(teacher_client, seed, {s["student_id"]: "absent"},
                day=TODAY + timedelta(days=i))
    db = get_db(test_db)
    try:
        rows = attendance_service.low_attendance(db, threshold=75.0)
        match = [r for r in rows if r["student_id"] == s["student_id"]]
        assert match, "expected the student to be flagged"
        row = match[0]
        assert row["percentage"] == 25.0
        # need (1+n)/(4+n) >= 0.75 -> n >= 8
        assert row["classes_needed"] == 8
    finally:
        db.close()
