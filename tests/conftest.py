"""Shared pytest fixtures.

Tests run against a dedicated MySQL test database (TEST_MYSQL_DATABASE,
default: attendance_test) so the developer's real data is never touched.
The schema is reset once per session and re-seeded per test module.
"""
from __future__ import annotations

import os
import re

import pytest

os.environ.setdefault("APP_ENV", "testing")
os.environ.setdefault("FLASK_SECRET_KEY", "test-only-secret-key")
# Cheap hashing for tests only (seed fixtures run outside app context).
os.environ.setdefault("PASSWORD_HASH_METHOD", "pbkdf2:sha256:1000")

from app import create_app  # noqa: E402
from config import get_config  # noqa: E402
from database import db_manager  # noqa: E402
from database.db import get_db  # noqa: E402
from services.user_service import create_user  # noqa: E402


@pytest.fixture(scope="session")
def test_db():
    """Reset the dedicated test database once per session."""
    cfg = get_config("testing")()
    if not db_manager.wait_for_server(cfg, timeout=30):
        pytest.fail(
            "MySQL server is not reachable. Start it with: docker compose up -d mysql"
        )
    db_manager.reset_database(cfg)
    yield cfg


@pytest.fixture(scope="session")
def app(test_db):
    app = create_app("testing")
    app.config.update(TESTING=True)
    yield app


@pytest.fixture()
def client(app):
    with app.test_client() as c:
        yield c


@pytest.fixture()
def _fresh_clients(app):
    """Independent clients so multi-role tests don't share a session."""
    clients = []

    def make():
        c = app.test_client()
        clients.append(c)
        return c

    yield make
    # clients are closed automatically when the test client objects are GC'd


@pytest.fixture()
def admin_client(client, seed):
    login(client, "admin1", "adminpass")
    return client


@pytest.fixture()
def teacher_client(client, seed):
    login(client, "teacher1", "teachpass")
    return client


@pytest.fixture()
def student_client(client, seed):
    login(client, "student1", "studypass")
    return client


@pytest.fixture()
def multi(app, seed):
    """Factory for role-specific clients used together in one test."""
    def make(role):
        c = app.test_client()
        creds = {"admin": ("admin1", "adminpass"),
                 "teacher": ("teacher1", "teachpass"),
                 "teacher2": ("teacher2", "teachpass"),
                 "student": ("student1", "studypass"),
                 "student2": ("student2", "studypass"),
                 "student3": ("student3", "studypass")}
        username, password = creds[role]
        login(c, username, password)
        return c
    return make


def _csrf(client) -> str:
    """Extract a CSRF token even though TESTING disables enforcement."""
    page = client.get("/login")
    match = re.search(rb'name="csrf_token" value="([^"]+)"', page.data)
    return match.group(1).decode() if match else "test-token"


@pytest.fixture()
def seed(test_db):
    """Minimal academic data + users for one section, fresh per test."""
    cfg = test_db
    db = get_db(cfg)
    try:
        # Per-test isolation: clear all data left by earlier tests.
        db.execute("SET FOREIGN_KEY_CHECKS=0")
        for table in ("audit_logs", "notifications", "attendance_edits",
                      "qr_scan_events", "attendance", "attendance_sessions",
                      "leave_requests", "timetable", "teacher_subjects",
                      "students", "teachers", "subjects", "sections",
                      "classes", "users", "settings"):
            db.execute(f"TRUNCATE TABLE {table}")
        db.execute("SET FOREIGN_KEY_CHECKS=1")
        db.commit()

        db.execute("INSERT INTO classes (name) VALUES ('CSE')")
        class_id = db.query_value("SELECT class_id FROM classes WHERE name='CSE'")
        db.execute(
            "INSERT INTO sections (class_id, name) VALUES (%s, 'A')", (class_id,))
        section_id = db.query_value(
            "SELECT section_id FROM sections WHERE name='A'")
        for code, name in (("CS101", "Data Structures"),
                           ("CS102", "Operating Systems")):
            db.execute(
                "INSERT INTO subjects (code, name) VALUES (%s, %s)",
                (code, name))

        subject_ids = [r["subject_id"] for r in db.query(
            "SELECT subject_id FROM subjects ORDER BY subject_id")]

        create_user(db, "admin1", "admin", "adminpass", full_name="Admin One")
        create_user(db, "teacher1", "teacher", "teachpass",
                    full_name="Teacher One", subject_ids=subject_ids)
        teacher_id = db.query_value(
            "SELECT teacher_id FROM teachers t JOIN users u "
            "ON u.user_id=t.user_id WHERE u.username='teacher1'")
        # Second teacher (NOT assigned to the subjects) for authorization tests
        create_user(db, "teacher2", "teacher", "teachpass",
                    full_name="Teacher Two")
        for n in (1, 2, 3):
            create_user(db, f"student{n}", "student", "studypass",
                        full_name=f"Student {n}",
                        class_id=class_id, section_id=section_id,
                        register_number=f"REG{n:03d}")
        db.commit()
        yield {
            "class_id": class_id,
            "section_id": section_id,
            "subject_ids": subject_ids,
            "teacher_id": teacher_id,
        }
    finally:
        db.close()


def login(client, username, password):
    """Log a user in through the real login endpoint."""
    client.get("/login")
    return client.post(
        "/login",
        data={"username": username, "password": password},
        follow_redirects=False,
    )
