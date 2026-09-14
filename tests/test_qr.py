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


# ---------------------------------------------------------------------------
# Anti-proxy layers: geo fence, dynamic rotation, scan audit, device sharing
# ---------------------------------------------------------------------------

def _mint_geo_token(app, seed, *, lat, lon, radius=150, day=TODAY, period=6):
    """Create a geo-fenced session row directly and return its token."""
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
            "expires_at, require_geo, latitude, longitude, radius_m) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 1, %s, %s, %s)",
            (token_hash(token), seed["teacher_id"], seed["subject_ids"][0],
             seed["class_id"], seed["section_id"], day, period, expires,
             lat, lon, radius))
        db.commit()
    finally:
        db.close()
    return token


def test_geo_required_without_location_rejected(student_client, seed, app):
    token = _mint_geo_token(app, seed, lat=12.9716, lon=77.5946)
    response = _scan(student_client, token)
    assert b"Location is required" in response.data


def test_geo_fence_rejects_far_student(student_client, seed, app):
    token = _mint_geo_token(app, seed, lat=12.9716, lon=77.5946)
    # ~25 km away from the fence center.
    response = student_client.post(
        "/attendance/scan",
        data={"token": token, "latitude": "13.2100", "longitude": "77.7500"},
        follow_redirects=True)
    assert b"from the classroom" in response.data


def test_geo_fence_allows_nearby_student(student_client, seed, app):
    token = _mint_geo_token(app, seed, lat=12.9716, lon=77.5946)
    response = student_client.post(
        "/attendance/scan",
        data={"token": token, "latitude": "12.9717", "longitude": "77.5947"},
        follow_redirects=True)
    assert b"marked present" in response.data


def test_dynamic_rotation_still_validates(student_client, seed, app):
    """A rotated (step-N) token must validate even though the DB only
    stores the hash of the original token - that is the whole point of
    rotation resisting screenshot sharing."""
    from config import get_config
    from database.db import get_db
    from services import qr_service

    cfg = get_config("testing")()
    with app.app_context():
        db = get_db(cfg)
        try:
            token, _ = qr_service.start_session(
                db, teacher_id=seed["teacher_id"],
                subject_id=seed["subject_ids"][0], class_id=seed["class_id"],
                section_id=seed["section_id"], attendance_date=TODAY,
                period=7, dynamic=True)
            db.commit()
            sess = db.query_one(
                "SELECT * FROM attendance_sessions WHERE token_hash=%s",
                (qr_service.token_hash(token),))
            rotated, _ = qr_service.rotate_token(sess)
        finally:
            db.close()
    assert rotated != token
    response = _scan(student_client, rotated)
    assert b"marked present" in response.data


def test_scan_attempts_are_logged(student_client, seed, app, test_db):
    token = _mint_token(student_client.application, seed)
    _scan(student_client, token)                      # success
    _scan(student_client, token)                      # duplicate
    _scan(student_client, "forged.payload.deadbeef")  # rejected (no session)

    from config import get_config
    from database.db import get_db

    db = get_db(get_config("testing")())
    try:
        results = [r["result"] for r in db.query(
            "SELECT result FROM qr_scan_events ORDER BY scan_id")]
        reasons = [r["reason"] for r in db.query(
            "SELECT reason FROM qr_scan_events ORDER BY scan_id")]
    finally:
        db.close()
    assert results == ["success", "duplicate"]
    assert reasons[1] == "already marked"


def test_device_sharing_flagged(multi, seed, app, test_db):
    """Two students checking in from one device fingerprint is the
    screenshot-share signature and must be flagged."""
    token = _mint_token(app, seed)
    _scan(multi("student"), token)
    _scan(multi("student2"), token)  # test clients share the default UA

    from config import get_config
    from database.db import get_db
    from services import qr_service

    db = get_db(get_config("testing")())
    try:
        session_id = db.query_value(
            "SELECT MAX(session_id) FROM attendance_sessions")
        flagged = qr_service.suspicious_devices(db, session_id, threshold=1)
    finally:
        db.close()
    assert flagged and flagged[0]["students"] >= 2
