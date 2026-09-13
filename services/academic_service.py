"""Academic data: classes, sections, subjects, teacher assignments."""
from __future__ import annotations


def list_classes(db):
    return db.query(
        """
        SELECT c.class_id, c.name,
               (SELECT COUNT(*) FROM sections sec
                 WHERE sec.class_id = c.class_id) AS section_count
        FROM classes c ORDER BY c.name
        """
    )


def create_class(db, name: str) -> None:
    name = (name or "").strip()
    if not name or len(name) > 50:
        raise ValueError("Class name must be 1-50 characters.")
    if db.query_one("SELECT 1 FROM classes WHERE name=%s", (name,)):
        raise ValueError("A class with that name already exists.")
    db.execute("INSERT INTO classes (name) VALUES (%s)", (name,))


def delete_class(db, class_id: int) -> None:
    db.execute("DELETE FROM classes WHERE class_id=%s", (class_id,))


def sections_of_class(db, class_id: int):
    return db.query(
        """
        SELECT sec.section_id, sec.name, c.name AS class_name,
               (SELECT COUNT(*) FROM students s
                 WHERE s.section_id = sec.section_id) AS student_count
        FROM sections sec JOIN classes c ON c.class_id = sec.class_id
        WHERE sec.class_id = %s ORDER BY sec.name
        """,
        (class_id,),
    )


def create_section(db, class_id: int, name: str) -> None:
    name = (name or "").strip()
    if not name or len(name) > 20:
        raise ValueError("Section name must be 1-20 characters.")
    if db.query_one(
        "SELECT 1 FROM sections WHERE class_id=%s AND name=%s", (class_id, name)
    ):
        raise ValueError("That section already exists for this class.")
    db.execute(
        "INSERT INTO sections (class_id, name) VALUES (%s, %s)",
        (class_id, name),
    )


def delete_section(db, section_id: int) -> None:
    db.execute("DELETE FROM sections WHERE section_id=%s", (section_id,))


def list_subjects(db):
    return db.query(
        """
        SELECT s.subject_id, s.code, s.name,
               (SELECT COUNT(*) FROM teacher_subjects ts
                 WHERE ts.subject_id = s.subject_id) AS teacher_count
        FROM subjects s ORDER BY s.name
        """
    )


def create_subject(db, name: str, code: str | None = None) -> None:
    name = (name or "").strip()
    code = (code or "").strip() or None
    if not name or len(name) > 100:
        raise ValueError("Subject name must be 1-100 characters.")
    if db.query_one("SELECT 1 FROM subjects WHERE name=%s", (name,)):
        raise ValueError("A subject with that name already exists.")
    if code and db.query_one("SELECT 1 FROM subjects WHERE code=%s", (code,)):
        raise ValueError("A subject with that code already exists.")
    db.execute(
        "INSERT INTO subjects (name, code) VALUES (%s, %s)", (name, code)
    )


def delete_subject(db, subject_id: int) -> None:
    db.execute("DELETE FROM subjects WHERE subject_id=%s", (subject_id,))


def assign_teacher_subjects(db, teacher_id: int, subject_ids) -> None:
    db.execute(
        "DELETE FROM teacher_subjects WHERE teacher_id=%s", (teacher_id,)
    )
    for sid in subject_ids or []:
        db.execute(
            "INSERT IGNORE INTO teacher_subjects (teacher_id, subject_id) "
            "VALUES (%s, %s)",
            (teacher_id, sid),
        )


def teacher_assignment_map(db) -> dict[int, list[int]]:
    mapping: dict[int, list[int]] = {}
    for row in db.query(
        "SELECT teacher_id, subject_id FROM teacher_subjects"
    ):
        mapping.setdefault(row["teacher_id"], []).append(row["subject_id"])
    return mapping


def list_teachers(db):
    return db.query(
        """
        SELECT t.teacher_id, t.department, u.username,
               COALESCE(u.full_name, u.username) AS display_name
        FROM teachers t JOIN users u ON u.user_id = t.user_id
        ORDER BY display_name
        """
    )
