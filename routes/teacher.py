"""Teacher routes: attendance marking, history, QR sessions, leaves."""
from __future__ import annotations

from datetime import date as date_cls

from flask import (
    Blueprint, current_app, flash, redirect, render_template, request,
    session, url_for,
)

from database.db import DatabaseError, get_db
from security.core import login_required, role_required
from services import attendance_service, audit_service, leave_service
from services import notification_service as notify_svc
from services import qr_service, timetable_service

bp = Blueprint("teacher", __name__)


def _teacher_id(db) -> int | None:
    return attendance_service.get_teacher_id(db, session["user_id"])


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

@bp.route("/teacher/dashboard")
@login_required
@role_required("teacher")
def dashboard():
    db = get_db()
    try:
        teacher_id = _teacher_id(db)
        if not teacher_id:
            flash("Teacher profile not found. Contact the admin.", "error")
            return redirect(url_for("dashboard.dashboard"))

        subjects = attendance_service.teacher_subjects(db, teacher_id)
        classes = sorted({
            (row["class_name"], row["section_name"])
            for row in db.query(
                """
                SELECT DISTINCT c.name AS class_name, sec.name AS section_name
                FROM timetable tt
                JOIN classes c ON c.class_id = tt.class_id
                JOIN sections sec ON sec.section_id = tt.section_id
                WHERE tt.teacher_id = %s
                """,
                (teacher_id,),
            )
        })
        today = attendance_service.today_counts(db, teacher_id=teacher_id)
        pending = db.query_value(
            """
            SELECT COUNT(*) FROM leave_requests lr
            JOIN students st ON st.student_id = lr.student_id
            WHERE lr.status = 'pending'
              AND (lr.teacher_id = %s OR EXISTS (
                    SELECT 1 FROM timetable tt
                    WHERE tt.section_id = st.section_id
                      AND tt.teacher_id = %s))
            """,
            (teacher_id, teacher_id),
        ) or 0
        low = attendance_service.low_attendance(
            db, section_id=None, subject_id=None, limit=10)
        timetable = timetable_service.timetable_for_teacher(db, teacher_id)
        return render_template(
            "teacher/dashboard.html", subjects=subjects, classes=classes,
            today=today, pending=pending, low=low, timetable=timetable,
            days=timetable_service.DAYS)
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Mark attendance
# ---------------------------------------------------------------------------

@bp.route("/mark_attendance", methods=["GET", "POST"])
@login_required
@role_required("teacher")
def mark_attendance():
    db = get_db()
    try:
        teacher_id = _teacher_id(db)
        if not teacher_id:
            flash("Teacher profile not found.", "error")
            return redirect(url_for("dashboard.dashboard"))

        subjects = attendance_service.teacher_subjects(db, teacher_id)
        pairs = attendance_service.class_sections(db)

        if request.method == "POST":
            section_id = request.form.get("section_id", type=int)
            subject_id = request.form.get("subject_id", type=int)
            attendance_date = request.form.get("attendance_date") \
                or date_cls.today().isoformat()
            period = request.form.get("period", 1, type=int) or 1

            if not section_id or not subject_id:
                flash("Choose a section and a subject.", "error")
                return redirect(url_for("teacher.mark_attendance"))
            if not attendance_service.teacher_is_assigned(db, teacher_id,
                                                          subject_id):
                flash("You are not assigned to this subject.", "error")
                return redirect(url_for("teacher.mark_attendance"))

            # Existing marks for pre-filling the roster.
            existing = {
                r["student_id"]: r["status"]
                for r in db.query(
                    """
                    SELECT student_id, status FROM attendance
                    WHERE subject_id=%s AND attendance_date=%s AND period=%s
                    """,
                    (subject_id, attendance_date, period),
                )
            }
            students = attendance_service.students_of_section(db, section_id)
            for s in students:
                s["marked_status"] = existing.get(s["student_id"])
            sel_section = next(
                (p for p in pairs if p["section_id"] == section_id), None)
            return render_template(
                "teacher/mark_attendance.html", students=students,
                subjects=subjects, pairs=pairs, selected_section=section_id,
                selected_subject=subject_id, selected_date=attendance_date,
                selected_period=period, selected_label=sel_section)

        return render_template("teacher/mark_attendance.html", students=None,
                               subjects=subjects, pairs=pairs,
                               selected_date=date_cls.today().isoformat())
    finally:
        db.close()


@bp.route("/submit_attendance", methods=["POST"])
@login_required
@role_required("teacher")
def submit_attendance():
    section_id = request.form.get("section_id", type=int)
    subject_id = request.form.get("subject_id", type=int)
    attendance_date = request.form.get("attendance_date")
    period = request.form.get("period", 1, type=int) or 1

    statuses = {}
    for key, value in request.form.items():
        if key.startswith("status_"):
            statuses[int(key.split("_", 1)[1])] = value

    db = get_db()
    try:
        teacher_id = _teacher_id(db)
        if not teacher_id:
            flash("Teacher profile not found.", "error")
            return redirect(url_for("dashboard.dashboard"))
        if not attendance_service.teacher_is_assigned(db, teacher_id,
                                                      subject_id or 0):
            flash("You are not assigned to this subject.", "error")
            return redirect(url_for("teacher.mark_attendance"))

        count = attendance_service.mark_attendance(
            db, teacher_id=teacher_id, subject_id=subject_id,
            class_id=request.form.get("class_id", type=int),
            section_id=section_id, attendance_date=attendance_date,
            period=period, statuses=statuses)
        audit_service.log_action(
            db, session["user_id"], "mark_attendance", "subject", subject_id,
            f"Marked {count} students for {attendance_date} period {period}")
        db.commit()
        flash(f"Attendance saved for {count} students.", "success")
    except DatabaseError:
        db.rollback()
        current_app.logger.exception("Attendance submit failed")
        flash("Could not save attendance. Please try again.", "error")
    finally:
        db.close()
    return redirect(url_for("teacher.view_attendance"))


# ---------------------------------------------------------------------------
# View / edit attendance
# ---------------------------------------------------------------------------

@bp.route("/view_attendance")
@login_required
@role_required("teacher")
def view_attendance():
    page = request.args.get("page", 1, type=int)
    filters = {
        "subject_id": request.args.get("subject_id", type=int),
        "section_id": request.args.get("section_id", type=int),
        "start_date": request.args.get("start_date") or None,
        "end_date": request.args.get("end_date") or None,
        "status": request.args.get("status") or None,
    }
    db = get_db()
    try:
        teacher_id = _teacher_id(db)
        rows, total, pages = attendance_service.teacher_history(
            db, teacher_id, page=page, **filters)
        return render_template(
            "teacher/view_attendance.html", rows=rows, total=total,
            page=page, pages=pages, subjects=attendance_service.teacher_subjects(
                db, teacher_id),
            pairs=attendance_service.class_sections(db), **filters)
    finally:
        db.close()


@bp.route("/attendance/<int:attendance_id>/edit", methods=["GET", "POST"])
@login_required
@role_required("teacher")
def edit_attendance(attendance_id):
    db = get_db()
    try:
        teacher_id = _teacher_id(db)
        record = attendance_service.attendance_record_for_teacher(
            db, attendance_id, teacher_id)
        if not record:
            flash("Attendance record not found (or not yours to edit).",
                  "error")
            return redirect(url_for("teacher.view_attendance"))

        if request.method == "POST":
            new_status = attendance_service.normalize_status(
                request.form.get("status"))
            reason = (request.form.get("reason") or "").strip() or None
            if not new_status:
                flash("Invalid status.", "error")
                return redirect(request.url)
            if new_status != record["status"]:
                attendance_service.record_edit(
                    db, attendance_id, record["status"], new_status,
                    session["user_id"], reason)
                db.execute(
                    "UPDATE attendance SET status=%s, marked_by=%s "
                    "WHERE attendance_id=%s",
                    (new_status, session["user_id"], attendance_id))
                audit_service.log_action(
                    db, session["user_id"], "edit_attendance",
                    "attendance", attendance_id,
                    f"Status {record['status']} -> {new_status}"
                    + (f" ({reason})" if reason else ""))
                db.commit()
                flash("Attendance updated.", "success")
            else:
                flash("Status unchanged.", "info")
            return redirect(url_for("teacher.view_attendance"))
        return render_template("teacher/edit_attendance.html", record=record)
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Attendance summary + low attendance
# ---------------------------------------------------------------------------

@bp.route("/attendance_summary")
@login_required
@role_required("teacher")
def attendance_summary():
    section_id = request.args.get("section_id", type=int)
    subject_id = request.args.get("subject_id", type=int)
    db = get_db()
    try:
        teacher_id = _teacher_id(db)
        rows = attendance_service.section_summary(
            db, section_id, subject_id) if section_id else []
        return render_template(
            "teacher/attendance_summary.html", rows=rows,
            subjects=attendance_service.teacher_subjects(db, teacher_id),
            pairs=attendance_service.class_sections(db),
            selected_section=section_id, selected_subject=subject_id)
    finally:
        db.close()


@bp.route("/low_attendance")
@login_required
@role_required("teacher")
def low_attendance():
    threshold = request.args.get("threshold", 75.0, type=float)
    section_id = request.args.get("section_id", type=int)
    subject_id = request.args.get("subject_id", type=int)
    db = get_db()
    try:
        teacher_id = _teacher_id(db)
        rows = attendance_service.low_attendance(
            db, threshold=threshold, section_id=section_id,
            subject_id=subject_id)
        return render_template(
            "teacher/low_attendance.html", rows=rows, threshold=threshold,
            subjects=attendance_service.teacher_subjects(db, teacher_id),
            pairs=attendance_service.class_sections(db),
            selected_section=section_id, selected_subject=subject_id)
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Leave requests
# ---------------------------------------------------------------------------

@bp.route("/teacher/leave_requests")
@login_required
@role_required("teacher")
def leave_requests():
    db = get_db()
    try:
        teacher_id = _teacher_id(db)
        rows = leave_service.teacher_requests(db, teacher_id)
        return render_template("teacher/leave_requests.html", rows=rows)
    finally:
        db.close()


@bp.route("/leave_requests/<int:leave_id>/decide", methods=["POST"])
@login_required
@role_required("teacher")
def decide_leave(leave_id):
    decision = request.form.get("decision")
    db = get_db()
    try:
        teacher_id = _teacher_id(db)
        try:
            leave_service.decide(db, leave_id, teacher_id, decision)
            row = db.query_one(
                """
                SELECT lr.status, u.user_id, u.username
                FROM leave_requests lr
                JOIN students st ON st.student_id = lr.student_id
                JOIN users u ON u.user_id = st.user_id
                WHERE lr.leave_id = %s
                """,
                (leave_id,),
            )
            audit_service.log_action(db, session["user_id"],
                                     f"{decision}_leave", "leave", leave_id,
                                     f"Leave {decision} by teacher")
            if row:
                notify_svc.notify(
                    db, row["user_id"],
                    f"Leave request {decision}",
                    f"Your leave request #{leave_id} was {decision}.",
                    "leave")
            db.commit()
            flash(f"Leave request {decision}.", "success")
        except ValueError as exc:
            db.rollback()
            flash(str(exc), "error")
    finally:
        db.close()
    return redirect(url_for("teacher.leave_requests"))


# ---------------------------------------------------------------------------
# QR attendance sessions
# ---------------------------------------------------------------------------

@bp.route("/attendance/session/new", methods=["GET", "POST"])
@login_required
@role_required("teacher")
def new_session():
    db = get_db()
    try:
        teacher_id = _teacher_id(db)
        subjects = attendance_service.teacher_subjects(db, teacher_id)
        pairs = attendance_service.class_sections(db)

        if request.method == "POST":
            section_id = request.form.get("section_id", type=int)
            subject_id = request.form.get("subject_id", type=int)
            period = request.form.get("period", 1, type=int) or 1
            attendance_date = request.form.get("attendance_date") \
                or date_cls.today().isoformat()
            sel = next((p for p in pairs if p["section_id"] == section_id),
                       None)
            if not sel or not attendance_service.teacher_is_assigned(
                    db, teacher_id, subject_id or 0):
                flash("Invalid section or subject selection.", "error")
                return redirect(request.url)
            try:
                token, expires = qr_service.start_session(
                    db, teacher_id=teacher_id, subject_id=subject_id,
                    class_id=sel["class_id"], section_id=section_id,
                    attendance_date=attendance_date, period=period)
                db.commit()
            except DatabaseError:
                db.rollback()
                flash("Could not start the session.", "error")
                return redirect(request.url)
            qr_uri = qr_service.qr_png_data_uri(token)
            return render_template(
                "teacher/qr_session.html", qr_uri=qr_uri, expires=expires,
                minutes=current_app.config["QR_SESSION_MINUTES"],
                subject_id=subject_id, section_label=sel["label"],
                attendance_date=attendance_date, period=period)

        return render_template("teacher/new_session.html", subjects=subjects,
                               pairs=pairs,
                               today=date_cls.today().isoformat())
    finally:
        db.close()


@bp.route("/attendance/session/<int:session_id>/end", methods=["POST"])
@login_required
@role_required("teacher")
def end_session(session_id):
    db = get_db()
    try:
        teacher_id = _teacher_id(db)
        cur = db.execute(
            "UPDATE attendance_sessions SET is_active=0 "
            "WHERE session_id=%s AND teacher_id=%s",
            (session_id, teacher_id))
        db.commit()
        flash("Session ended.", "success")
    finally:
        db.close()
    return redirect(url_for("teacher.dashboard"))


# ---------------------------------------------------------------------------
# Timetable (view only for teachers)
# ---------------------------------------------------------------------------

@bp.route("/teacher/timetable")
@login_required
@role_required("teacher")
def timetable():
    db = get_db()
    try:
        teacher_id = _teacher_id(db)
        rows = timetable_service.timetable_for_teacher(db, teacher_id)
        return render_template("teacher/timetable.html", rows=rows,
                               days=timetable_service.DAYS)
    finally:
        db.close()
