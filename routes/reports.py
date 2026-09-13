"""Reports: filtered views + Excel / CSV / PDF exports with authorization."""
from __future__ import annotations

from datetime import date as date_cls

from flask import (
    Blueprint, current_app, flash, redirect, render_template, request,
    send_file, session, url_for,
)

from database.db import get_db
from security.core import login_required, role_required
from services import attendance_service, report_service

bp = Blueprint("reports", __name__)


def _filters():
    return {
        "section_id": request.args.get("section_id", type=int)
        or request.form.get("section_id", type=int),
        "subject_id": request.args.get("subject_id", type=int)
        or request.form.get("subject_id", type=int),
        "start_date": request.values.get("start_date") or None,
        "end_date": request.values.get("end_date") or None,
        "status": request.values.get("status") or None,
    }


def _teacher_guard(db, f) -> int | None:
    """Teachers may only report on subjects assigned to them."""
    if session.get("role") == "teacher":
        teacher_id = attendance_service.get_teacher_id(db, session["user_id"])
        if f.get("subject_id") and not attendance_service.teacher_is_assigned(
                db, teacher_id, f["subject_id"]):
            return None
        return teacher_id
    return None


@bp.route("/reports")
@login_required
@role_required("admin", "teacher")
def index():
    f = _filters()
    db = get_db()
    try:
        teacher_id = _teacher_guard(db, f)
        if session.get("role") == "teacher" and f.get("subject_id") \
                and teacher_id is None:
            flash("You are not assigned to that subject.", "error")
            return redirect(url_for("reports.index"))

        rows = report_service.attendance_rows(db, teacher_id=teacher_id, **f)
        summary_rows = report_service.student_summary_rows(
            db, section_id=f["section_id"], subject_id=f["subject_id"],
            teacher_id=teacher_id)
        subjects = attendance_service.teacher_subjects(db, teacher_id) \
            if teacher_id else db.query(
                "SELECT subject_id, name FROM subjects ORDER BY name")
        return render_template(
            "reports/index.html", rows=rows, summary_rows=summary_rows,
            subjects=subjects, pairs=attendance_service.class_sections(db),
            f=f, today=date_cls.today().isoformat())
    finally:
        db.close()


@bp.route("/reports/export")
@login_required
@role_required("admin", "teacher")
def export():
    f = _filters()
    file_type = request.args.get("file_type", "excel")
    db = get_db()
    try:
        teacher_id = _teacher_guard(db, f)
        if session.get("role") == "teacher" and f.get("subject_id") \
                and teacher_id is None:
            flash("You are not assigned to that subject.", "error")
            return redirect(url_for("reports.index"))

        rows = report_service.attendance_rows(db, teacher_id=teacher_id, **f)
        if not rows:
            flash("No attendance records match the selected filters.",
                  "warning")
            return redirect(url_for("reports.index"))

        stamp = date_cls.today().isoformat()
        summary = {
            "Records": len(rows),
            "Present": sum(1 for r in rows if r["status"] == "present"),
            "Absent": sum(1 for r in rows if r["status"] == "absent"),
            "Leave": sum(1 for r in rows if r["status"] == "leave"),
        }
        subtitle = (
            f"Filters: section={f['section_id'] or 'all'}, "
            f"subject={f['subject_id'] or 'all'}, "
            f"{f['start_date'] or 'beginning'} to {f['end_date'] or stamp}"
        )

        if file_type == "csv":
            buf = report_service.to_csv(rows)
            return send_file(buf, as_attachment=True,
                             download_name=f"attendance_report_{stamp}.csv",
                             mimetype="text/csv")
        if file_type == "pdf":
            buf = report_service.to_pdf(
                "Attendance Report", subtitle, rows, summary)
            return send_file(buf, as_attachment=True,
                             download_name=f"attendance_report_{stamp}.pdf",
                             mimetype="application/pdf")
        buf = report_service.to_excel(rows)
        return send_file(buf, as_attachment=True,
                         download_name=f"attendance_report_{stamp}.xlsx",
                         mimetype=("application/vnd.openxmlformats-"
                                   "officedocument.spreadsheetml.sheet"))
    finally:
        db.close()


@bp.route("/reports/low_attendance/export")
@login_required
@role_required("admin", "teacher")
def export_low_attendance():
    threshold = request.args.get("threshold", 75.0, type=float)
    section_id = request.args.get("section_id", type=int)
    subject_id = request.args.get("subject_id", type=int)
    db = get_db()
    try:
        teacher_id = None
        if session.get("role") == "teacher":
            teacher_id = attendance_service.get_teacher_id(db,
                                                           session["user_id"])
            if subject_id and not attendance_service.teacher_is_assigned(
                    db, teacher_id, subject_id):
                flash("You are not assigned to that subject.", "error")
                return redirect(url_for("teacher.low_attendance"))

        rows = attendance_service.low_attendance(
            db, threshold=threshold, section_id=section_id,
            subject_id=subject_id)
        if not rows:
            flash("No students below the threshold.", "info")
            return redirect(url_for("teacher.low_attendance")
                            if teacher_id else url_for("reports.index"))

        export_rows = [{
            "Student": r["display_name"],
            "Class": r.get("class_name") or "",
            "Section": r.get("section_name") or "",
            "Subject": r.get("subject_name") or "",
            "Total": r["total"],
            "Attended": r["attended"],
            "Percentage": f"{r['percentage']}%",
            "Classes needed": r["classes_needed"],
        } for r in rows]
        buf = report_service.to_excel(export_rows, sheet="Low Attendance")
        return send_file(buf, as_attachment=True,
                         download_name="low_attendance_report.xlsx",
                         mimetype=("application/vnd.openxmlformats-"
                                   "officedocument.spreadsheetml.sheet"))
    finally:
        db.close()
