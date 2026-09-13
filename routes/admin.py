"""Admin routes: user management, academic data, audit logs."""
from __future__ import annotations

from flask import (
    Blueprint, current_app, flash, redirect, render_template, request,
    session, url_for,
)

from database.db import DatabaseError, get_db
from security.core import login_required, role_required
from services import academic_service, audit_service, user_service

bp = Blueprint("admin", __name__, url_prefix="/admin")


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

@bp.route("/dashboard")
@login_required
@role_required("admin")
def dashboard():
    db = get_db()
    try:
        stats = {
            "students": db.query_value(
                "SELECT COUNT(*) FROM users WHERE role='student'") or 0,
            "teachers": db.query_value(
                "SELECT COUNT(*) FROM users WHERE role='teacher'") or 0,
            "subjects": db.query_value("SELECT COUNT(*) FROM subjects") or 0,
            "classes": db.query_value("SELECT COUNT(*) FROM classes") or 0,
        }
        teacher_subjects = db.query(
            """
            SELECT t.teacher_id, u.username,
                   COALESCE(u.full_name, u.username) AS display_name,
                   GROUP_CONCAT(s.name ORDER BY s.name SEPARATOR ', ') AS subjects
            FROM teachers t
            JOIN users u ON u.user_id = t.user_id
            LEFT JOIN teacher_subjects ts ON ts.teacher_id = t.teacher_id
            LEFT JOIN subjects s ON s.subject_id = ts.subject_id
            GROUP BY t.teacher_id, u.username
            ORDER BY display_name
            """
        )
        return render_template("admin/dashboard.html", stats=stats,
                               teacher_subjects=teacher_subjects)
    finally:
        db.close()


# ---------------------------------------------------------------------------
# User management
# ---------------------------------------------------------------------------

@bp.route("/users")
@login_required
@role_required("admin")
def users():
    page = request.args.get("page", 1, type=int)
    search = request.args.get("search", "").strip()
    role = request.args.get("role", "").strip()
    db = get_db()
    try:
        rows, total, pages = user_service.list_users(
            db, search=search or None, role=role or None, page=page)
        return render_template("admin/users.html", users=rows, total=total,
                               page=page, pages=pages, search=search,
                               role=role)
    finally:
        db.close()


@bp.route("/users/add", methods=["GET", "POST"])
@login_required
@role_required("admin")
def add_user():
    db = get_db()
    try:
        if request.method == "POST":
            try:
                user_id = user_service.create_user(
                    db,
                    username=request.form.get("username"),
                    role=request.form.get("role"),
                    password=request.form.get("password"),
                    full_name=request.form.get("full_name") or None,
                    email=request.form.get("email") or None,
                    class_id=request.form.get("class_id", type=int),
                    section_id=request.form.get("section_id", type=int),
                    register_number=request.form.get("register_number") or None,
                    department=request.form.get("department") or None,
                    subject_ids=request.form.getlist("subject_ids"),
                )
                audit_service.log_action(db, session["user_id"], "create_user",
                                         "user", user_id,
                                         f"Created {request.form.get('role')} "
                                         f"account {request.form.get('username')}")
                db.commit()
                flash(f"User '{request.form.get('username')}' created.",
                      "success")
                return redirect(url_for("admin.users"))
            except ValueError as exc:
                db.rollback()
                flash(str(exc), "error")
            except DatabaseError:
                db.rollback()
                flash("Could not create the user (database error).", "error")

        subjects = academic_service.list_subjects(db)
        classes = academic_service.list_classes(db)
        sections = db.query(
            """
            SELECT sec.section_id, sec.name, sec.class_id, c.name AS class_name
            FROM sections sec JOIN classes c ON c.class_id = sec.class_id
            ORDER BY c.name, sec.name
            """
        )
        return render_template("admin/add_user.html", subjects=subjects,
                               classes=classes, sections=sections)
    finally:
        db.close()


@bp.route("/users/<int:user_id>/edit", methods=["GET", "POST"])
@login_required
@role_required("admin")
def edit_user(user_id):
    db = get_db()
    try:
        if request.method == "POST":
            try:
                user_service.update_user(
                    db, user_id,
                    username=request.form.get("username"),
                    role=request.form.get("role"),
                    password=request.form.get("password") or None,
                    full_name=request.form.get("full_name") or None,
                    class_id=request.form.get("class_id", type=int),
                    section_id=request.form.get("section_id", type=int),
                    register_number=request.form.get("register_number") or None,
                    department=request.form.get("department") or None,
                    subject_ids=request.form.getlist("subject_ids"),
                )
                db.commit()
                flash("User updated.", "success")
                return redirect(url_for("admin.users"))
            except ValueError as exc:
                db.rollback()
                flash(str(exc), "error")

        user = user_service.get_user_with_profile(db, user_id)
        if not user:
            flash("User not found.", "error")
            return redirect(url_for("admin.users"))
        subjects = academic_service.list_subjects(db)
        classes = academic_service.list_classes(db)
        sections = db.query(
            """
            SELECT sec.section_id, sec.name, sec.class_id, c.name AS class_name
            FROM sections sec JOIN classes c ON c.class_id = sec.class_id
            ORDER BY c.name, sec.name
            """
        )
        assigned = []
        if user["role"] == "teacher":
            t = db.query_one(
                "SELECT teacher_id FROM teachers WHERE user_id=%s", (user_id,))
            if t:
                assigned = [r["subject_id"] for r in db.query(
                    "SELECT subject_id FROM teacher_subjects WHERE teacher_id=%s",
                    (t["teacher_id"],))]
        return render_template("admin/edit_user.html", user=user,
                               subjects=subjects, classes=classes,
                               sections=sections, assigned=assigned)
    finally:
        db.close()


@bp.route("/users/<int:user_id>/delete", methods=["POST"])
@login_required
@role_required("admin")
def delete_user(user_id):
    if user_id == session.get("user_id"):
        flash("You cannot delete your own account.", "error")
        return redirect(url_for("admin.users"))
    db = get_db()
    try:
        row = db.query_one("SELECT username FROM users WHERE user_id=%s",
                           (user_id,))
        if not row:
            flash("User not found.", "error")
            return redirect(url_for("admin.users"))
        db.execute("DELETE FROM users WHERE user_id=%s", (user_id,))
        audit_service.log_action(db, session["user_id"], "delete_user",
                                 "user", user_id, f"Deleted user {row['username']}")
        db.commit()
        flash(f"User '{row['username']}' deleted.", "success")
    except DatabaseError:
        db.rollback()
        flash("Could not delete the user.", "error")
    finally:
        db.close()
    return redirect(url_for("admin.users"))


@bp.route("/users/<int:user_id>/reset_password", methods=["GET", "POST"])
@login_required
@role_required("admin")
def reset_password(user_id):
    db = get_db()
    try:
        user = db.query_one(
            "SELECT user_id, username FROM users WHERE user_id=%s", (user_id,))
        if not user:
            flash("User not found.", "error")
            return redirect(url_for("admin.users"))
        if request.method == "POST":
            try:
                from services.user_service import hash_password, \
                    validate_password_strength
                pwd = request.form.get("password") or ""
                if err := validate_password_strength(pwd):
                    raise ValueError(err)
                db.execute(
                    "UPDATE users SET password_hash=%s WHERE user_id=%s",
                    (hash_password(pwd), user_id))
                audit_service.log_action(
                    db, session["user_id"], "reset_password", "user", user_id,
                    f"Password reset for {user['username']}")
                db.commit()
                flash(f"Password updated for '{user['username']}'.", "success")
                return redirect(url_for("admin.users"))
            except ValueError as exc:
                db.rollback()
                flash(str(exc), "error")
        return render_template("admin/reset_password.html", user=user)
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Bulk import (CSV / Excel)
# ---------------------------------------------------------------------------

@bp.route("/users/import", methods=["GET", "POST"])
@login_required
@role_required("admin")
def import_users():
    import csv as csv_mod
    from pathlib import Path

    import pandas as pd
    from werkzeug.utils import secure_filename

    if request.method == "GET":
        return render_template("admin/import_users.html")

    file = request.files.get("file")
    if not file or file.filename == "":
        flash("Please choose a CSV or Excel file.", "error")
        return redirect(request.url)
    ext = file.filename.rsplit(".", 1)[-1].lower()
    if ext not in current_app.config["ALLOWED_EXTENSIONS"]:
        flash("Only .csv, .xls and .xlsx files are allowed.", "error")
        return redirect(request.url)

    upload_dir = Path(current_app.config["UPLOAD_FOLDER"])
    upload_dir.mkdir(parents=True, exist_ok=True)
    path = upload_dir / secure_filename(file.filename)
    file.save(path)

    created, failed = 0, 0
    db = get_db()
    try:
        try:
            if ext in ("xlsx", "xls"):
                frame = pd.read_excel(path, dtype=str)
                records = frame.where(frame.notna(), None).values.tolist()
            else:
                with open(path, newline="", encoding="utf-8-sig") as fh:
                    reader = csv_mod.reader(fh)
                    next(reader, None)  # header
                    records = list(reader)

            for row in records:
                if not row or len(row) < 3 or not (row[0] or "").strip():
                    failed += 1
                    continue
                try:
                    user_service.create_user(
                        db,
                        username=row[0], role=row[1], password=row[2],
                        class_id=int(row[3]) if len(row) > 3 and row[3] else None,
                        section_id=int(row[4]) if len(row) > 4 and row[4] else None,
                    )
                    created += 1
                except (ValueError, TypeError):
                    failed += 1
            db.commit()
        finally:
            path.unlink(missing_ok=True)

        if failed:
            flash(f"Imported {created} users; {failed} rows were skipped "
                  "(check usernames, roles and passwords).", "warning")
        else:
            flash(f"Imported {created} users.", "success")
        return redirect(url_for("admin.users"))
    except DatabaseError:
        db.rollback()
        flash("Database error during import.", "error")
        return redirect(url_for("admin.users"))
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Academic data: classes, sections, subjects, assignments
# ---------------------------------------------------------------------------

@bp.route("/academic")
@login_required
@role_required("admin")
def academic():
    db = get_db()
    try:
        classes = academic_service.list_classes(db)
        for c in classes:
            c["sections"] = academic_service.sections_of_class(db, c["class_id"])
        subjects = academic_service.list_subjects(db)
        return render_template("admin/academic.html", classes=classes,
                               subjects=subjects)
    finally:
        db.close()


@bp.route("/classes/add", methods=["POST"])
@login_required
@role_required("admin")
def add_class():
    db = get_db()
    try:
        try:
            academic_service.create_class(db, request.form.get("name"))
            db.commit()
            audit_service.log_action(db, session["user_id"], "create_class",
                                     "class", None, request.form.get("name"))
            db.commit()
            flash("Class created.", "success")
        except ValueError as exc:
            db.rollback()
            flash(str(exc), "error")
    finally:
        db.close()
    return redirect(url_for("admin.academic"))


@bp.route("/classes/<int:class_id>/delete", methods=["POST"])
@login_required
@role_required("admin")
def delete_class(class_id):
    db = get_db()
    try:
        academic_service.delete_class(db, class_id)
        db.commit()
        flash("Class deleted.", "success")
    finally:
        db.close()
    return redirect(url_for("admin.academic"))


@bp.route("/sections/add", methods=["POST"])
@login_required
@role_required("admin")
def add_section():
    db = get_db()
    try:
        try:
            academic_service.create_section(
                db, request.form.get("class_id", type=int),
                request.form.get("name"))
            db.commit()
            flash("Section created.", "success")
        except ValueError as exc:
            db.rollback()
            flash(str(exc), "error")
    finally:
        db.close()
    return redirect(url_for("admin.academic"))


@bp.route("/sections/<int:section_id>/delete", methods=["POST"])
@login_required
@role_required("admin")
def delete_section(section_id):
    db = get_db()
    try:
        academic_service.delete_section(db, section_id)
        db.commit()
        flash("Section deleted.", "success")
    finally:
        db.close()
    return redirect(url_for("admin.academic"))


@bp.route("/subjects/add", methods=["POST"])
@login_required
@role_required("admin")
def add_subject():
    db = get_db()
    try:
        try:
            academic_service.create_subject(db, request.form.get("name"),
                                            request.form.get("code"))
            db.commit()
            audit_service.log_action(db, session["user_id"], "create_subject",
                                     "subject", None, request.form.get("name"))
            db.commit()
            flash("Subject created.", "success")
        except ValueError as exc:
            db.rollback()
            flash(str(exc), "error")
    finally:
        db.close()
    return redirect(url_for("admin.academic"))


@bp.route("/subjects/<int:subject_id>/delete", methods=["POST"])
@login_required
@role_required("admin")
def delete_subject(subject_id):
    db = get_db()
    try:
        academic_service.delete_subject(db, subject_id)
        db.commit()
        flash("Subject deleted.", "success")
    finally:
        db.close()
    return redirect(url_for("admin.academic"))


@bp.route("/assignments", methods=["GET", "POST"])
@login_required
@role_required("admin")
def assignments():
    db = get_db()
    try:
        if request.method == "POST":
            teacher_id = request.form.get("teacher_id", type=int)
            subject_ids = [int(s) for s in request.form.getlist("subject_ids")]
            if not teacher_id:
                flash("Please choose a teacher.", "error")
            else:
                academic_service.assign_teacher_subjects(db, teacher_id,
                                                         subject_ids)
                audit_service.log_action(db, session["user_id"],
                                         "assign_teacher", "teacher",
                                         teacher_id,
                                         f"Assigned {len(subject_ids)} subjects")
                db.commit()
                flash("Subject assignments updated.", "success")
                return redirect(url_for("admin.assignments"))

        teachers = academic_service.list_teachers(db)
        subjects = academic_service.list_subjects(db)
        assignment_map = academic_service.teacher_assignment_map(db)
        return render_template("admin/assignments.html", teachers=teachers,
                               subjects=subjects, assignment_map=assignment_map)
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Audit logs
# ---------------------------------------------------------------------------

@bp.route("/audit")
@login_required
@role_required("admin")
def audit():
    page = request.args.get("page", 1, type=int)
    filters = {
        "user_id": request.args.get("user_id", type=int),
        "action": request.args.get("action", "").strip() or None,
        "date": request.args.get("date", "").strip() or None,
        "entity_type": request.args.get("entity_type", "").strip() or None,
    }
    db = get_db()
    try:
        rows, total, pages = audit_service.list_audit(db, page=page, **filters)
        users = db.query(
            "SELECT user_id, username FROM users ORDER BY username")
        return render_template("admin/audit.html", rows=rows, total=total,
                               page=page, pages=pages, users=users,
                               **filters)
    finally:
        db.close()
