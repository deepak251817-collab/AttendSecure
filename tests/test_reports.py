"""Report generation and export tests."""
from __future__ import annotations

from datetime import date, timedelta

from database.db import get_db
from services import attendance_service

TODAY = date.today()


def _seed_attendance(teacher_client, seed, test_db):
    db = get_db(test_db)
    try:
        students = attendance_service.students_of_section(
            db, seed["section_id"])
    finally:
        db.close()
    for i, s in enumerate(students):
        status = "present" if i % 2 == 0 else "absent"
        day = TODAY + timedelta(days=1)
        db = get_db(test_db)
        try:
            db.execute(
                "INSERT INTO attendance (student_id, subject_id, teacher_id, "
                "class_id, attendance_date, period, status) "
                "VALUES (%s, %s, %s, %s, %s, 1, %s)",
                (s["student_id"], seed["subject_ids"][0],
                 seed["teacher_id"], seed["class_id"], day, status))
            db.commit()
        finally:
            db.close()
    return students


def test_reports_page_renders(admin_client, seed, test_db):
    _seed_attendance(admin_client, seed, test_db)
    response = admin_client.get("/reports")
    assert response.status_code == 200
    assert b"Reports" in response.data


def test_report_date_filtering(admin_client, seed, test_db):
    _seed_attendance(admin_client, seed, test_db)
    day = (TODAY + timedelta(days=1)).isoformat()
    response = admin_client.get(f"/reports?start_date={day}&end_date={day}")
    assert response.status_code == 200
    assert b"badge-present" in response.data or b"badge-absent" in response.data


def test_report_class_filtering(admin_client, seed, test_db):
    _seed_attendance(admin_client, seed, test_db)
    response = admin_client.get(
        f"/reports?section_id={seed['section_id']}")
    assert response.status_code == 200


def test_excel_export(admin_client, seed, test_db):
    _seed_attendance(admin_client, seed, test_db)
    response = admin_client.get("/reports/export?file_type=excel")
    assert response.status_code == 200
    assert response.mimetype.startswith(
        "application/vnd.openxmlformats-officedocument")


def test_csv_export(admin_client, seed, test_db):
    _seed_attendance(admin_client, seed, test_db)
    response = admin_client.get("/reports/export?file_type=csv")
    assert response.status_code == 200
    assert b"student_name" in response.data or b"Student Name" in \
        response.data


def test_pdf_export(admin_client, seed, test_db):
    _seed_attendance(admin_client, seed, test_db)
    response = admin_client.get("/reports/export?file_type=pdf")
    assert response.status_code == 200
    assert response.data[:5] == b"%PDF-"


def test_export_without_data_redirects_with_warning(admin_client, seed):
    response = admin_client.get("/reports/export?file_type=excel",
                                follow_redirects=True)
    assert b"No attendance records" in response.data


def test_teacher_report_limited_to_own_subjects(client, seed, test_db):
    _seed_attendance(client, seed, test_db)
    from tests.conftest import login
    login(client, "teacher2", "teachpass")
    # teacher2 is not assigned to any subject; requesting the assigned
    # subject's export must be refused.
    response = client.get(
        f"/reports/export?file_type=excel&subject_id={seed['subject_ids'][0]}",
        follow_redirects=True)
    assert b"not assigned" in response.data
