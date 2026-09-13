"""Timetable and academic data tests."""
from __future__ import annotations

from database.db import get_db
from services import timetable_service


def test_admin_can_create_class(admin_client, seed):
    response = admin_client.post("/admin/classes/add",
                                 data={"name": "ECE"},
                                 follow_redirects=True)
    assert b"created" in response.data


def test_duplicate_class_rejected(admin_client, seed):
    response = admin_client.post("/admin/classes/add", data={"name": "CSE"},
                                 follow_redirects=True)
    assert b"already exists" in response.data


def test_admin_can_create_subject(admin_client, seed):
    response = admin_client.post("/admin/subjects/add",
                                 data={"code": "CS201",
                                       "name": "Computer Networks"},
                                 follow_redirects=True)
    assert b"created" in response.data


def test_duplicate_subject_rejected(admin_client, seed):
    response = admin_client.post("/admin/subjects/add",
                                 data={"name": "Data Structures"},
                                 follow_redirects=True)
    assert b"already exists" in response.data


def test_admin_can_assign_subjects(admin_client, seed, test_db):
    response = admin_client.post(
        "/admin/assignments",
        data={"teacher_id": str(seed["teacher_id"]),
              "subject_ids": [str(seed["subject_ids"][0])]},
        follow_redirects=True)
    assert b"updated" in response.data
    db = get_db(test_db)
    try:
        count = db.query_value(
            "SELECT COUNT(*) FROM teacher_subjects WHERE teacher_id=%s",
            (seed["teacher_id"],))
        assert count == 1
    finally:
        db.close()


def test_timetable_conflict_same_slot(teacher_client, seed, test_db):
    db = get_db(test_db)
    try:
        db.execute(
            "INSERT INTO timetable (class_id, section_id, subject_id, "
            "teacher_id, day_of_week, period, start_time, end_time) "
            "VALUES (%s, %s, %s, %s, 1, 1, '09:00:00', '09:45:00')",
            (seed["class_id"], seed["section_id"], seed["subject_ids"][0],
             seed["teacher_id"]))
        db.commit()
        errors = timetable_service.validate_entry(
            db, class_id=seed["class_id"], section_id=seed["section_id"],
            subject_id=seed["subject_ids"][1], teacher_id=seed["teacher_id"],
            day_of_week=1, period=1, start_time="09:00", end_time="09:45")
    finally:
        db.close()
    assert any("already has" in e for e in errors)


def test_timetable_conflict_teacher_double_booked(teacher_client, seed,
                                                  test_db):
    db = get_db(test_db)
    try:
        db.execute(
            "INSERT INTO timetable (class_id, section_id, subject_id, "
            "teacher_id, day_of_week, period, start_time, end_time) "
            "VALUES (%s, %s, %s, %s, 2, 2, '10:00:00', '10:45:00')",
            (seed["class_id"], seed["section_id"], seed["subject_ids"][0],
             seed["teacher_id"]))
        db.commit()
        errors = timetable_service.validate_entry(
            db, class_id=seed["class_id"], section_id=seed["section_id"],
            subject_id=seed["subject_ids"][0], teacher_id=seed["teacher_id"],
            day_of_week=2, period=3, start_time="10:30", end_time="11:15")
    finally:
        db.close()
    assert any("already teaches" in e for e in errors)


def test_timetable_valid_entry_passes(teacher_client, seed, test_db):
    db = get_db(test_db)
    try:
        errors = timetable_service.validate_entry(
            db, class_id=seed["class_id"], section_id=seed["section_id"],
            subject_id=seed["subject_ids"][0], teacher_id=seed["teacher_id"],
            day_of_week=3, period=4, start_time="11:00", end_time="11:45")
        assert errors == []
    finally:
        db.close()


def test_student_sees_own_timetable(student_client, seed, test_db):
    db = get_db(test_db)
    try:
        db.execute(
            "INSERT INTO timetable (class_id, section_id, subject_id, "
            "teacher_id, day_of_week, period, start_time, end_time) "
            "VALUES (%s, %s, %s, %s, 4, 1, '09:00:00', '09:45:00')",
            (seed["class_id"], seed["section_id"], seed["subject_ids"][0],
             seed["teacher_id"]))
        db.commit()
    finally:
        db.close()
    response = student_client.get("/student/timetable")
    assert response.status_code == 200
    assert b"Data Structures" in response.data


def test_teacher_sees_only_own_timetable(client, seed, test_db):
    db = get_db(test_db)
    try:
        db.execute(
            "INSERT INTO timetable (class_id, section_id, subject_id, "
            "teacher_id, day_of_week, period, start_time, end_time) "
            "VALUES (%s, %s, %s, %s, 5, 1, '09:00:00', '09:45:00')",
            (seed["class_id"], seed["section_id"], seed["subject_ids"][0],
             seed["teacher_id"]))
        db.commit()
    finally:
        db.close()
    from tests.conftest import login
    login(client, "teacher1", "teachpass")
    page = client.get("/teacher/timetable")
    assert b"Data Structures" in page.data
    login(client, "teacher2", "teachpass")
    page = client.get("/teacher/timetable")
    assert b"No timetable entries" in page.data
