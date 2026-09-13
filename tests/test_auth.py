"""Authentication tests: login, logout, role restrictions."""
from __future__ import annotations

from tests.conftest import login


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.get_json()["status"] == "ok"


def test_login_page_loads(client):
    response = client.get("/login")
    assert response.status_code == 200
    assert b"Sign In" in response.data


def test_successful_login_redirects_to_dashboard(client, seed):
    response = login(client, "admin1", "adminpass")
    assert response.status_code == 302
    assert "/dashboard" in response.headers["Location"]


def test_invalid_login_rejected(client, seed):
    response = login(client, "admin1", "wrong-password")
    assert response.status_code == 401


def test_unknown_user_rejected(client, seed):
    response = login(client, "ghost", "whatever")
    assert response.status_code == 401


def test_logout_clears_session(client, seed):
    login(client, "admin1", "adminpass")
    response = client.get("/logout")
    assert response.status_code == 302
    assert client.get("/dashboard").status_code == 302  # back to login


def test_unauthenticated_route_access_blocked(client, seed):
    for path in ("/dashboard", "/admin/users", "/mark_attendance",
                 "/student/dashboard", "/reports"):
        assert client.get(path).status_code == 302, path


def test_role_restriction_student_cannot_open_admin(client, seed):
    login(client, "student1", "studypass")
    assert client.get("/admin/users").status_code == 403
    assert client.get("/mark_attendance").status_code == 403


def test_role_restriction_teacher_cannot_open_admin(client, seed):
    login(client, "teacher1", "teachpass")
    assert client.get("/admin/users").status_code == 403
    assert client.get("/admin/audit").status_code == 403


def test_role_restriction_admin_cannot_mark_attendance(client, seed):
    login(client, "admin1", "adminpass")
    assert client.get("/mark_attendance").status_code == 403
