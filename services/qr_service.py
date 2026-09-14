"""QR attendance sessions with anti-proxy hardening.

Validation layers, in the order the server evaluates them:

1. Signed, expiring token (HMAC-SHA256; only its sha256 is stored).
2. Dynamic rotation - the QR re-renders with a fresh nonce every few
   seconds, so a screenshot loses value within seconds and screenshots
   shared through chat can be told apart by their nonce timestamps.
3. Server-side session validation (exists, active, not expired).
4. Class/section membership of the scanning student.
5. Optional geolocation fence (distance from the teacher's position).
6. Duplicate prevention (database unique constraint).
7. Device-sharing detection - many students checking in from one device
   fingerprint within a session is flagged for the teacher.
8. Audit: every scan attempt (success, duplicate or rejected) is recorded
   in qr_scan_events for review.

No layer claims to make proxy attendance impossible; together they raise
the effort and leave a trail.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import time
from datetime import date as date_cls
from datetime import datetime, timedelta

from flask import current_app, request

_SECRET = None


def _secret() -> bytes:
    global _SECRET
    if _SECRET is None:
        _SECRET = current_app.secret_key.encode()
    return _SECRET


def _sign(payload_b64: str) -> str:
    return hmac.new(_secret(), payload_b64.encode(), hashlib.sha256).hexdigest()


# ---------------------------------------------------------------------------
# Tokens (dynamic: carry a rotating nonce)
# ---------------------------------------------------------------------------

def create_token(teacher_id, subject_id, class_id, section_id,
                 attendance_date, period, session_nonce: str | None = None,
                 step: int | None = None) -> tuple[str, datetime]:
    """Build a signed, expiring QR payload. The DB stores only its sha256.

    ``session_nonce`` ties every rotation of one session together;
    ``step`` is the rotation counter (used for display ordering only -
    any recent step validates until the session expires).
    """
    if isinstance(attendance_date, str):
        attendance_date = date_cls.fromisoformat(attendance_date)
    expires = datetime.now() + timedelta(
        minutes=current_app.config["QR_SESSION_MINUTES"]
    )
    payload = {
        "t": teacher_id, "s": subject_id, "c": class_id, "sec": section_id,
        "d": attendance_date.isoformat(), "p": int(period),
        "e": int(expires.timestamp()),
        "n": session_nonce or secrets.token_hex(8),
        "r": int(step if step is not None else time.time()),
    }
    body = json.dumps(payload, separators=(",", ":"))
    token = f"{body}.{_sign(body)}"
    return token, expires


def parse_token(token: str) -> dict | None:
    """Return the payload dict if the signature and expiry are valid."""
    try:
        body, sig = token.rsplit(".", 1)
        if not hmac.compare_digest(sig, _sign(body)):
            return None
        payload = json.loads(body)
        if payload["e"] < time.time():
            return None
        return payload
    except (ValueError, KeyError, TypeError):
        return None


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


# ---------------------------------------------------------------------------
# Geolocation fence
# ---------------------------------------------------------------------------

def _earth_distance_m(lat1, lon1, lat2, lon2) -> float:
    """Great-circle distance in meters (haversine)."""
    import math

    r = 6_371_000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def distance_from_fence(sess, lat, lon) -> float | None:
    """Meters from the session's fence center, or None if no fence."""
    if lat is None or lon is None or sess.get("latitude") is None:
        return None
    return _earth_distance_m(float(sess["latitude"]), float(sess["longitude"]),
                             float(lat), float(lon))


def geo_error(sess, lat, lon) -> tuple[float | None, str | None]:
    """Return (distance_m, error). error is set when outside the fence."""
    if not sess.get("require_geo"):
        return None, None
    if lat is None or lon is None:
        return None, ("Location is required for this session. Allow location "
                      "access in your browser and try again.")
    dist = distance_from_fence(sess, lat, lon)
    radius = sess.get("radius_m") or 150
    if dist is not None and dist > radius:
        return dist, (f"You appear to be {int(dist)} m from the classroom "
                      f"(allowed: {radius} m).")
    return dist, None


# ---------------------------------------------------------------------------
# Device fingerprint (heuristic client hints, salted server-side)
# ---------------------------------------------------------------------------

def device_fingerprint() -> str:
    """Salted hash of coarse client hints. Deliberately weak alone; it only
    feeds the sharing heuristic, never a hard rejection."""
    ua = request.headers.get("User-Agent", "") if request else ""
    lang = request.headers.get("Accept-Language", "") if request else ""
    platform = ""
    if request is not None:
        platform = request.headers.get("Sec-CH-UA-Platform", "") or ""
    raw = f"{ua}|{lang}|{platform}"
    salted = hmac.new(_secret(), raw.encode(), hashlib.sha256).hexdigest()
    return salted


def suspicious_devices(db, session_id, threshold: int | None = None) -> list[dict]:
    """Device fingerprints used by more than `threshold` students in a
    session - the classic screenshot-share signature."""
    threshold = threshold or current_app.config.get("QR_DEVICE_SHARE_THRESHOLD", 2)
    return db.query(
        """
        SELECT device_hash, COUNT(DISTINCT student_id) AS students,
               GROUP_CONCAT(DISTINCT student_id) AS student_ids
        FROM qr_scan_events
        WHERE session_id = %s AND device_hash IS NOT NULL
        GROUP BY device_hash
        HAVING students > %s
        ORDER BY students DESC
        """,
        (session_id, threshold),
    )


# ---------------------------------------------------------------------------
# Session lifecycle
# ---------------------------------------------------------------------------

def start_session(db, *, teacher_id, subject_id, class_id, section_id,
                  attendance_date, period, require_geo=False,
                  latitude=None, longitude=None, radius_m=None,
                  dynamic=True) -> tuple[str, datetime]:
    """Create an attendance session row; return (token, expires_at).

    With ``dynamic`` the session gets a shared nonce; every rotation of the
    QR embeds that nonce with a fresh step, and any recent rotation
    validates server-side until the session expires.
    """
    session_nonce = secrets.token_hex(8) if dynamic else None
    token, expires = create_token(teacher_id, subject_id, class_id,
                                  section_id, attendance_date, period,
                                  session_nonce=session_nonce,
                                  step=0 if dynamic else None)
    db.execute(
        """
        INSERT INTO attendance_sessions
            (token_hash, teacher_id, subject_id, class_id, section_id,
             attendance_date, period, expires_at, dynamic_qr, session_nonce,
             require_geo, latitude, longitude, radius_m)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (token_hash(token), teacher_id, subject_id, class_id, section_id,
         attendance_date, period, expires, 1 if dynamic else 0,
         session_nonce, 1 if require_geo else 0, latitude, longitude,
         radius_m),
    )
    return token, expires


def rotate_token(sess) -> tuple[str, datetime] | None:
    """Fresh token for an active session (same nonce, new step)."""
    if not sess.get("dynamic_qr") or not sess.get("session_nonce"):
        return None
    return create_token(
        sess["teacher_id"], sess["subject_id"], sess["class_id"],
        sess["section_id"], sess["attendance_date"], sess["period"],
        session_nonce=sess["session_nonce"], step=int(time.time()))


def validate_session(db, token: str):
    """Server-side validation of a scanned QR token.

    Returns (session_row, error_message). Exactly one of the two is None.
    Checks signature, expiry, DB existence and active flag.
    """
    payload = parse_token(token)
    if not payload:
        return None, "Invalid or expired QR code."

    row = db.query_one(
        "SELECT * FROM attendance_sessions WHERE token_hash = %s",
        (token_hash(token),),
    )
    if not row and payload.get("n"):
        # Rotating tokens: any rotation of the same session validates while
        # the session is active. The nonce groups the session's rotations.
        row = db.query_one(
            """
            SELECT * FROM attendance_sessions
            WHERE session_nonce = %s AND is_active = 1
            """,
            (payload["n"],),
        )
    if not row or not row["is_active"]:
        return None, "Attendance session not found or no longer active."
    if row["expires_at"] < datetime.now():
        db.execute(
            "UPDATE attendance_sessions SET is_active=0 WHERE session_id=%s",
            (row["session_id"],),
        )
        return None, "This attendance session has expired."

    return row, None


def record_scan(db, sess, *, student_id=None, user_id=None, result="success",
                reason=None) -> None:
    """Persist one scan attempt (success, duplicate or rejected)."""
    lat = request.form.get("latitude", type=float) if request else None
    lon = request.form.get("longitude", type=float) if request else None
    dist = distance_from_fence(sess, lat, lon) if sess else None
    db.execute(
        """
        INSERT INTO qr_scan_events
            (session_id, student_id, user_id, result, reason, device_hash,
             latitude, longitude, distance_m, ip_address)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (sess["session_id"] if sess else None, student_id, user_id, result,
         (reason or "")[:120] or None,
         device_fingerprint() if request else None,
         lat, lon, int(dist) if dist is not None else None,
         request.remote_addr if request else None),
    )


def qr_png_data_uri(token: str) -> str:
    """Render the token as a QR PNG data URI (qrcode + pillow)."""
    import io
    import base64

    import qrcode

    img = qrcode.make(token)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()
