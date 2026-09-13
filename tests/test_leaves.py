"""Leave request workflow tests."""
from __future__ import annotations

from datetime import date, timedelta

TOMORROW = date.today() + timedelta(days=1)
DAY_AFTER = date.today() + timedelta(days=2)


def _submit_leave(client, start=TOMORROW, end=DAY_AFTER,
                  reason="Family event"):
    return client.post(
        "/student/leave_requests",
        data={"start_date": start.isoformat(), "end_date": end.isoformat(),
              "reason": reason},
        follow_redirects=True,
    )


def test_student_can_create_leave(student_client, seed):
    response = _submit_leave(student_client)
    assert b"submitted" in response.data


def test_invalid_leave_rejected(student_client, seed):
    response = _submit_leave(student_client, start=DAY_AFTER, end=TOMORROW)
    assert b"cannot be before" in response.data


def test_blank_reason_rejected(student_client, seed):
    response = _submit_leave(student_client, reason="   ")
    assert b"reason" in response.data


def test_overlapping_pending_leave_rejected(student_client, seed):
    first = _submit_leave(student_client)
    assert b"submitted" in first.data
    second = _submit_leave(student_client)
    assert b"overlaps" in second.data


def test_assigned_teacher_can_approve(multi, seed):
    student = multi("student")
    teacher = multi("teacher")
    _submit_leave(student)
    page = teacher.get("/teacher/leave_requests")
    assert b"Family event" in page.data
    response = teacher.post(
        "/leave_requests/1/decide", data={"decision": "approved"},
        follow_redirects=True)
    assert b"approved" in response.data


def test_assigned_teacher_can_reject(multi, seed):
    student = multi("student")
    teacher = multi("teacher")
    _submit_leave(student)
    response = teacher.post(
        "/leave_requests/1/decide", data={"decision": "rejected"},
        follow_redirects=True)
    assert b"rejected" in response.data


def test_unrelated_teacher_cannot_decide(multi, seed):
    student = multi("student")
    teacher2 = multi("teacher2")
    _submit_leave(student)
    response = teacher2.post("/leave_requests/1/decide",
                             data={"decision": "approved"},
                             follow_redirects=True)
    assert b"not authorized" in response.data


def test_already_decided_leave_cannot_be_redecided(multi, seed):
    student = multi("student")
    teacher = multi("teacher")
    _submit_leave(student)
    teacher.post("/leave_requests/1/decide", data={"decision": "approved"})
    response = teacher.post("/leave_requests/1/decide",
                            data={"decision": "rejected"},
                            follow_redirects=True)
    assert b"already been decided" in response.data


def test_student_sees_leave_status(multi, seed):
    student = multi("student")
    teacher = multi("teacher")
    _submit_leave(student)
    teacher.post("/leave_requests/1/decide", data={"decision": "approved"})
    page = student.get("/student/leave_requests")
    assert b"badge-approved" in page.data
    # Decision notification was created for the student
    unread = student.get("/notifications/unread_count")
    assert unread.get_json()["count"] >= 1
