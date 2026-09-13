"""QR attendance session tests."""
from __future__ import annotations

from datetime import date, timedelta

from database.db import get_db

TODAY = date.today()


def _start_session(teacher_client, seed, day=TODAY, period=3):
    return teacher_client.post(
        "/attendance/session/new",
        data={"section_id": str(seed["section_id"]),
              "subject_id": str(seed["subject_ids"][0]),
              "attendance_date": day.isoformat(),
              "period": str(period)},
    )


def _mint_token(app, seed, day=TODAY, period=3):
    """Create a session row directly and return its token."""
    from config import get_config
    from database.db import get_db
    from services import qr_service
    from services.qr_service import token_hash

    cfg = get_config("testing")()
    with app.app_context():
        token, expires = qr_service.create_token(
            seed["teacher_id"], seed["subject_ids"][0], seed["class_id"],
            seed["section_id"], day, period)
    db = get_db(cfg)
    try:
        db.execute(
            "INSERT INTO attendance_sessions (token_hash, teacher_id, "
            "subject_id, class_id, section_id, attendance_date, period, "
            "expires_at) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
            (token_hash(token), seed["teacher_id"], seed["subject_ids"][0],
             seed["class_id"], seed["section_id"], day, period, expires))
        db.commit()
    finally:
        db.close()
    return token


def _scan(student_client, token):
    return student_client.post("/attendance/scan", data={"token": token},
                               follow_redirects=True)


def test_session_page_shows_qr(teacher_client, seed):
    response = _start_session(teacher_client, seed)
    assert response.status_code == 200
    assert b"data:image/png;base64" in response.data


def test_valid_qr_marks_present(student_client, seed):
    token = _mint_token(student_client.application, seed)
    response = _scan(student_client, token)
    assert b"marked present" in response.data


def test_duplicate_qr_rejected(student_client, seed):
    token = _mint_token(student_client.application, seed)
    first = _scan(student_client, token)
    assert b"marked present" in first.data
    second = _scan(student_client, token)
    assert b"already recorded" in second.data


def test_expired_qr_rejected(client, seed, app):
    from config import get_config
    from database.db import get_db
    from services import qr_service
    from services.qr_service import token_hash
    from datetime import datetime, timedelta

    yesterday = TODAY - timedelta(days=1)
    with app.app_context():
        token, _ = qr_service.create_token(
            seed["teacher_id"], seed["subject_ids"][0], seed["class_id"],
            seed["section_id"], yesterday, 3)
    cfg = get_config("testing")()
    db = get_db(cfg)
    try:
        db.execute(
            "INSERT INTO attendance_sessions (token_hash, teacher_id, "
            "subject_id, class_id, section_id, attendance_date, period, "
            "expires_at, is_active) VALUES (%s, %s, %s, %s, %s, %s, 3, %s, 1)",
            (token_hash(token), seed["teacher_id"], seed["subject_ids"][0],
             seed["class_id"], seed["section_id"], yesterday,
             datetime.now() - timedelta(minutes=1)))
        db.commit()
    finally:
        db.close()

    from tests.conftest import login
    login(client, "student1", "studypass")
    response = client.post("/attendance/scan", data={"token": token},
                           follow_redirects=True)
    assert b"expired" in response.data


def test_forged_qr_rejected(student_client, seed):
    response = _scan(student_client, "forged.payload.deadbeef")
    assert b"Invalid or expired" in response.data


def test_qr_from_wrong_class_rejected(student_client, seed, app, test_db):
    # A token minted for a different section must not validate for ours.
    db = get_db(test_db)
    try:
        db.execute("INSERT INTO classes (name) VALUES ('OTHER')")
        other_class = db.query_value(
            "SELECT class_id FROM classes WHERE name='OTHER'")
        db.execute(
            "INSERT INTO sections (class_id, name) VALUES (%s, 'Z')",
            (other_class,))
        other_section = db.query_value(
            "SELECT section_id FROM sections WHERE name='Z'")
        db.commit()
    finally:
        db.close()
    other_seed = dict(seed)
    other_seed["section_id"] = other_section
    other_seed["class_id"] = other_class
    token = _mint_token(app, other_seed)
    response = _scan(student_client, token)
    assert b"not for your class" in response.data


def test_student_of_other_section_cannot_use_qr(multi, seed, app):
    token = _mint_token(app, seed)
    student3 = multi("student3")  # same section -> should pass
    response = student3.post("/attendance/scan", data={"token": token},
                             follow_redirects=True)
    assert b"marked present" in response.data or \
        b"already recorded" in response.data
