"""Notification and audit log tests."""
from __future__ import annotations


def test_notification_created_on_leave_decision(multi, seed):
    student = multi("student")
    teacher = multi("teacher")
    student.post(
        "/student/leave_requests",
        data={"start_date": "2099-01-01", "end_date": "2099-01-02",
              "reason": "Conference"},
        follow_redirects=True)
    teacher.post("/leave_requests/1/decide", data={"decision": "approved"})
    unread = student.get("/notifications/unread_count")
    assert unread.get_json()["count"] >= 1


def test_unread_count_starts_at_zero(student_client, seed):
    unread = student_client.get("/notifications/unread_count")
    assert unread.get_json()["count"] == 0


def test_mark_single_notification_read(multi, seed):
    student = multi("student")
    teacher = multi("teacher")
    student.post(
        "/student/leave_requests",
        data={"start_date": "2099-01-05", "end_date": "2099-01-06",
              "reason": "Illness"},
        follow_redirects=True)
    teacher.post("/leave_requests/1/decide", data={"decision": "rejected"})
    assert student.get(
        "/notifications/unread_count").get_json()["count"] >= 1
    student.post("/notifications/1/read", follow_redirects=True)
    page = student.get("/notifications")
    assert b"Mark all as read" in page.data


def test_mark_all_read(student_client, seed):
    response = student_client.post("/notifications/read_all",
                                   follow_redirects=True)
    assert response.status_code == 200
    assert student_client.get(
        "/notifications/unread_count").get_json()["count"] == 0


def test_audit_log_records_login(admin_client, seed, test_db):
    from database.db import get_db
    db = get_db(test_db)
    try:
        count = db.query_value(
            "SELECT COUNT(*) FROM audit_logs WHERE action='login'")
        assert count >= 1
    finally:
        db.close()


def test_audit_log_records_user_creation(admin_client, seed, test_db):
    admin_client.post(
        "/admin/users/add",
        data={"username": "audituser", "role": "student",
              "password": "secret12"},
        follow_redirects=True)
    from database.db import get_db
    db = get_db(test_db)
    try:
        count = db.query_value(
            "SELECT COUNT(*) FROM audit_logs WHERE action='create_user'")
        assert count >= 1
    finally:
        db.close()


def test_audit_page_renders_with_filters(admin_client, seed):
    response = admin_client.get("/admin/audit?action=login")
    assert response.status_code == 200
    assert b"login" in response.data


def test_audit_hidden_from_non_admins(teacher_client, seed):
    assert teacher_client.get("/admin/audit").status_code == 403
