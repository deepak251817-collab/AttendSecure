"""Student routes: attendance views, leaves, QR check-in, profile."""
from __future__ import annotations

from flask import (
    Blueprint, current_app, flash, redirect, render_template, request,
    session, url_for,
)

from database.db import DatabaseError, get_db
from mysql.connector import Error as MySQLError
from security.core import login_required, role_required
from services import attendance_service, audit_service, leave_service
from services import notification_service as notify_svc
from services import qr_service, timetable_service
from services.user_service import change_own_password

bp = Blueprint("student", __name__)


def _student_id(db) -> int | None:
    return attendance_service.get_student_id(db, session["user_id"])


@bp.route("/student/dashboard")
@login_required
@role_required("student")
def dashboard():
    db = get_db()
    try:
        student_id = _student_id(db)
        if not student_id:
            flash("Student profile not found. Contact the admin.", "error")
            return redirect(url_for("dashboard.dashboard"))

        overall = attendance_service.overall_stats(db, student_id)
        by_subject = attendance_service.summary_by_subject(db, student_id)
        threshold = current_app.config["LOW_ATTENDANCE_THRESHOLD"]
        warnings = [s for s in by_subject
                    if s["percentage"] < threshold]
        recent = db.query(
            """
            SELECT a.attendance_date, a.period, a.status, s.name AS subject_name
            FROM attendance a JOIN subjects s ON s.subject_id = a.subject_id
            WHERE a.student_id = %s
            ORDER BY a.attendance_date DESC, a.period DESC LIMIT 10
            """,
            (student_id,),
        )
        leaves = leave_service.student_requests(db, student_id)[:5]
        return render_template(
            "student/dashboard.html", overall=overall, by_subject=by_subject,
            warnings=warnings, threshold=threshold, recent=recent,
            leaves=leaves)
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Attendance views
# ---------------------------------------------------------------------------

@bp.route("/student/my_attendance")
@login_required
@role_required("student")
def my_attendance():
    subject_id = request.args.get("subject_id", type=int)
    status = request.args.get("status") or None
    start_date = request.args.get("start_date") or None
    end_date = request.args.get("end_date") or None
    page = request.args.get("page", 1, type=int)
    per_page = 25

    db = get_db()
    try:
        student_id = _student_id(db)
        rows, total = attendance_service.history(
            db, student_id, limit=per_page,
            offset=(page - 1) * per_page, subject_id=subject_id,
            status=status, start_date=start_date, end_date=end_date)
        pages = (total + per_page - 1) // per_page
        return render_template(
            "student/my_attendance.html", rows=rows, total=total, page=page,
            pages=pages, overall=attendance_service.overall_stats(db, student_id),
            by_subject=attendance_service.summary_by_subject(db, student_id),
            subjects=db.query(
                "SELECT subject_id, name FROM subjects ORDER BY name"),
            selected_subject=subject_id, selected_status=status,
            start_date=start_date, end_date=end_date)
    finally:
        db.close()


@bp.route("/attendance/monthly")
@login_required
@role_required("student")
def monthly():
    db = get_db()
    try:
        student_id = _student_id(db)
        trend = attendance_service.monthly_trend(db, student_id)
        overall = attendance_service.overall_stats(db, student_id)
        return render_template("student/monthly.html", trend=trend,
                               overall=overall)
    finally:
        db.close()


@bp.route("/student/timetable")
@login_required
@role_required("student")
def timetable():
    db = get_db()
    try:
        student_id = _student_id(db)
        section_id = db.query_value(
            "SELECT section_id FROM students WHERE student_id=%s",
            (student_id,))
        rows = timetable_service.timetable_for_section(db, section_id) \
            if section_id else []
        return render_template("student/timetable.html", rows=rows,
                               days=timetable_service.DAYS)
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Leave requests
# ---------------------------------------------------------------------------

@bp.route("/student/leave_requests", methods=["GET", "POST"])
@login_required
@role_required("student")
def leave_requests():
    db = get_db()
    try:
        student_id = _student_id(db)
        if request.method == "POST":
            try:
                leave_id = leave_service.create_request(
                    db, student_id,
                    request.form.get("start_date"),
                    request.form.get("end_date"),
                    request.form.get("reason"),
                    subject_id=request.form.get("subject_id", type=int))
                db.commit()
                audit_service.log_action(db, session["user_id"],
                                         "create_leave", "leave", leave_id,
                                         "Student submitted leave request")
                db.commit()
                flash("Leave request submitted.", "success")
                return redirect(url_for("student.leave_requests"))
            except ValueError as exc:
                db.rollback()
                flash(str(exc), "error")
            except DatabaseError:
                db.rollback()
                flash("Could not submit the request.", "error")

        subjects = db.query(
            """
            SELECT DISTINCT s.subject_id, s.name
            FROM students st
            JOIN timetable tt ON tt.section_id = st.section_id
            JOIN subjects s ON s.subject_id = tt.subject_id
            WHERE st.student_id = %s ORDER BY s.name
            """,
            (student_id,),
        )
        rows = leave_service.student_requests(db, student_id)
        return render_template("student/leave_requests.html", rows=rows,
                               subjects=subjects)
    finally:
        db.close()


# ---------------------------------------------------------------------------
# QR check-in
# ---------------------------------------------------------------------------

@bp.route("/attendance/scan", methods=["GET", "POST"])
@login_required
@role_required("student")
def scan_qr():
    if request.method == "POST":
        token = (request.form.get("token") or "").strip()
        db = get_db()
        try:
            student_id = _student_id(db)
            sess, error = qr_service.validate_session(db, token)
            if error:
                flash(error, "error")
                return redirect(url_for("student.scan_qr"))

            # Student must belong to the session's class/section.
            student = db.query_one(
                "SELECT section_id, class_id FROM students WHERE student_id=%s",
                (student_id,),
            )
            if not student or student["section_id"] != sess["section_id"]:
                flash("This QR code is not for your class.", "error")
                return redirect(url_for("student.scan_qr"))

            # Duplicate protection is backed by the DB unique constraint.
            try:
                db.execute(
                    """
                    INSERT INTO attendance
                        (student_id, subject_id, teacher_id, class_id,
                         attendance_date, period, status, marked_by)
                    VALUES (%s, %s, %s, %s, %s, %s, 'present', NULL)
                    """,
                    (student_id, sess["subject_id"], sess["teacher_id"],
                     sess["class_id"], sess["attendance_date"],
                     sess["period"]),
                )
                db.commit()
            except MySQLError as exc:
                db.rollback()
                if getattr(exc, "errno", None) == 1062:
                    flash("Attendance already recorded for this session.",
                          "warning")
                    return redirect(url_for("student.dashboard"))
                current_app.logger.error("QR check-in failed: %s", exc)
                flash("Could not record attendance. Please try again.",
                      "error")
                return redirect(url_for("student.scan_qr"))

            notify_svc.notify(db, session["user_id"], "Attendance recorded",
                              f"Present for period {sess['period']} on "
                              f"{sess['attendance_date']}.", "attendance")
            db.commit()
            flash("Attendance recorded. You are marked present.", "success")
            return redirect(url_for("student.dashboard"))
        finally:
            db.close()
    return render_template("student/scan_qr.html")


# ---------------------------------------------------------------------------
# Profile
# ---------------------------------------------------------------------------

@bp.route("/profile", methods=["GET", "POST"])
@login_required
@role_required("student")
def profile():
    db = get_db()
    try:
        student_id = _student_id(db)
        if request.method == "POST":
            action = request.form.get("action")
            if action == "profile":
                full_name = (request.form.get("full_name") or "").strip()
                if not full_name:
                    flash("Name cannot be empty.", "error")
                else:
                    db.execute(
                        "UPDATE users SET full_name=%s WHERE user_id=%s",
                        (full_name[:120], session["user_id"]))
                    db.commit()
                    flash("Profile updated.", "success")
            elif action == "password":
                try:
                    change_own_password(
                        db, session["user_id"],
                        request.form.get("current_password"),
                        request.form.get("new_password"))
                    db.commit()
                    audit_service.log_action(db, session["user_id"],
                                             "change_password", "user",
                                             session["user_id"])
                    db.commit()
                    flash("Password changed.", "success")
                except ValueError as exc:
                    db.rollback()
                    flash(str(exc), "error")
            return redirect(url_for("student.profile"))

        user = db.query_one(
            """
            SELECT u.username, u.full_name, s.register_number,
                   c.name AS class_name, sec.name AS section_name
            FROM users u
            LEFT JOIN students s ON s.user_id = u.user_id
            LEFT JOIN classes c ON c.class_id = s.class_id
            LEFT JOIN sections sec ON sec.section_id = s.section_id
            WHERE u.user_id = %s
            """,
            (session["user_id"],),
        )
        return render_template("student/profile.html", user=user)
    finally:
        db.close()
