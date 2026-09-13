"""QR attendance sessions: signed tokens, expiry, server-side validation."""
from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import time
from datetime import date as date_cls
from datetime import datetime, timedelta

from flask import current_app

_SECRET = None


def _secret() -> bytes:
    global _SECRET
    if _SECRET is None:
        _SECRET = current_app.secret_key.encode()
    return _SECRET


def _sign(payload_b64: str) -> str:
    return hmac.new(_secret(), payload_b64.encode(), hashlib.sha256).hexdigest()


def create_token(teacher_id, subject_id, class_id, section_id,
                 attendance_date, period) -> tuple[str, datetime]:
    """Build a signed, expiring QR payload. The DB stores only its sha256."""
    if isinstance(attendance_date, str):
        attendance_date = date_cls.fromisoformat(attendance_date)
    expires = datetime.now() + timedelta(
        minutes=current_app.config["QR_SESSION_MINUTES"]
    )
    payload = {
        "t": teacher_id, "s": subject_id, "c": class_id, "sec": section_id,
        "d": attendance_date.isoformat(), "p": int(period),
        "e": int(expires.timestamp()), "n": secrets.token_hex(8),
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


def start_session(db, *, teacher_id, subject_id, class_id, section_id,
                  attendance_date, period) -> tuple[str, datetime] | None:
    """Create an attendance session row and return (token, expires_at)."""
    token, expires = create_token(teacher_id, subject_id, class_id,
                                  section_id, attendance_date, period)
    db.execute(
        """
        INSERT INTO attendance_sessions
            (token_hash, teacher_id, subject_id, class_id, section_id,
             attendance_date, period, expires_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (token_hash(token), teacher_id, subject_id, class_id, section_id,
         attendance_date, period, expires),
    )
    return token, expires


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
    if not row or not row["is_active"]:
        return None, "Attendance session not found or no longer active."
    if row["expires_at"] < datetime.now():
        db.execute(
            "UPDATE attendance_sessions SET is_active=0 WHERE session_id=%s",
            (row["session_id"],),
        )
        return None, "This attendance session has expired."

    return row, None


def qr_png_data_uri(token: str) -> str:
    """Render the token as a QR PNG data URI (qrcode + pillow)."""
    import io
    import base64

    import qrcode

    img = qrcode.make(token)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()
