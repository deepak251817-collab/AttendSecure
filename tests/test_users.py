"""User management tests (admin side)."""
from __future__ import annotations


def test_admin_can_create_student(admin_client, seed):
    response = admin_client.post(
        "/admin/users/add",
        data={
            "username": "newstudent",
            "full_name": "New Student",
            "role": "student",
            "password": "secret12",
            "class_id": str(seed["class_id"]),
            "section_id": str(seed["section_id"]),
            "register_number": "REG900",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"created" in response.data


def test_duplicate_username_rejected(admin_client, seed):
    response = admin_client.post(
        "/admin/users/add",
        data={
            "username": "student1",
            "role": "student",
            "password": "secret12",
        },
        follow_redirects=True,
    )
    assert b"already exists" in response.data


def test_invalid_role_rejected(admin_client, seed):
    response = admin_client.post(
        "/admin/users/add",
        data={"username": "sneaky", "role": "superadmin",
              "password": "secret12"},
        follow_redirects=True,
    )
    assert b"Invalid role" in response.data


def test_weak_password_rejected(admin_client, seed):
    response = admin_client.post(
        "/admin/users/add",
        data={"username": "weakpw", "role": "student", "password": "123"},
        follow_redirects=True,
    )
    assert b"at least 6" in response.data


def test_admin_can_create_teacher_with_subjects(admin_client, seed):
    response = admin_client.post(
        "/admin/users/add",
        data={
            "username": "newteacher",
            "role": "teacher",
            "password": "teach123",
            "subject_ids": [str(s) for s in seed["subject_ids"]],
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"created" in response.data


def test_admin_can_delete_user(admin_client, seed):
    response = admin_client.post(
        "/admin/users/3/delete", follow_redirects=True)
    assert b"deleted" in response.data


def test_admin_cannot_delete_self(admin_client, seed):
    response = admin_client.post("/admin/users/1/delete",
                                 follow_redirects=True)
    assert b"cannot delete your own" in response.data


def test_users_list_search_filters(admin_client, seed):
    response = admin_client.get("/admin/users?search=student2")
    assert response.status_code == 200
    assert b"student2" in response.data
