"""Report generation: query, aggregate, export to Excel / CSV / PDF."""
from __future__ import annotations

from datetime import date as date_cls
from io import BytesIO

from flask import current_app


def attendance_rows(db, *, section_id=None, subject_id=None, teacher_id=None,
                    start_date=None, end_date=None, status=None,
                    limit: int = 5000):
    """Filtered attendance rows shared by on-screen reports and exports."""
    where, params = ["1=1"], []
    if teacher_id is not None:
        where.append("ts.teacher_id = %s")
        params.append(teacher_id)
    if section_id:
        where.append("st.section_id = %s")
        params.append(section_id)
    if subject_id:
        where.append("a.subject_id = %s")
        params.append(subject_id)
    if status in ("present", "absent", "leave"):
        where.append("a.status = %s")
        params.append(status)
    if start_date:
        where.append("a.attendance_date >= %s")
        params.append(start_date)
    if end_date:
        where.append("a.attendance_date <= %s")
        params.append(end_date)
    return db.query(
        f"""
        SELECT a.attendance_id, a.attendance_date, a.period, a.status,
               u.username,
               COALESCE(u.full_name, u.username) AS student_name,
               st.register_number,
               sub.name AS subject_name,
               c.name AS class_name, sec.name AS section_name
        FROM attendance a
        JOIN students st ON st.student_id = a.student_id
        JOIN users u ON u.user_id = st.user_id
        JOIN subjects sub ON sub.subject_id = a.subject_id
        JOIN teacher_subjects ts ON ts.subject_id = a.subject_id
        LEFT JOIN sections sec ON sec.section_id = st.section_id
        LEFT JOIN classes c ON c.class_id = sec.class_id
        WHERE {' AND '.join(where)}
        ORDER BY a.attendance_date DESC, a.period, student_name
        LIMIT %s
        """,
        params + [limit],
    )


def student_summary_rows(db, *, section_id=None, subject_id=None,
                         teacher_id=None):
    where, params = ["1=1"], []
    if teacher_id is not None:
        where.append("ts.teacher_id = %s")
        params.append(teacher_id)
    if section_id:
        where.append("st.section_id = %s")
        params.append(section_id)
    if subject_id:
        where.append("a.subject_id = %s")
        params.append(subject_id)
    return db.query(
        f"""
        SELECT u.username,
               COALESCE(u.full_name, u.username) AS student_name,
               st.register_number, c.name AS class_name, sec.name AS section_name,
               COUNT(a.attendance_id) AS total,
               COALESCE(SUM(a.status='present'),0) AS present,
               COALESCE(SUM(a.status='absent'),0) AS absent,
               COALESCE(SUM(a.status='leave'),0) AS `leave`,
               CASE WHEN COUNT(a.attendance_id)=0 THEN 0
                    ELSE ROUND(100*SUM(a.status IN ('present','leave'))
                               /COUNT(a.attendance_id),2) END AS percentage
        FROM students st
        JOIN users u ON u.user_id = st.user_id
        LEFT JOIN sections sec ON sec.section_id = st.section_id
        LEFT JOIN classes c ON c.class_id = sec.class_id
        LEFT JOIN attendance a ON a.student_id = st.student_id
        LEFT JOIN subjects sub ON sub.subject_id = a.subject_id
        LEFT JOIN teacher_subjects ts ON ts.subject_id = a.subject_id
        WHERE {' AND '.join(where)}
        GROUP BY u.user_id, u.username, st.register_number, c.name, sec.name
        ORDER BY student_name
        """,
        params,
    )


# ---------------------------------------------------------------------------
# Exports
# ---------------------------------------------------------------------------

def to_excel(rows: list[dict], sheet: str = "Attendance") -> BytesIO:
    import pandas as pd

    df = pd.DataFrame(rows)
    if df.empty:
        df = pd.DataFrame(columns=["Date", "Period", "Student", "Register No",
                                   "Subject", "Class", "Section", "Status"])
    df.columns = [c.replace("_", " ").title() for c in df.columns]
    if "Attendance Date" in df.columns:
        df["Attendance Date"] = df["Attendance Date"].astype(str)
    buf = BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name=sheet)
    buf.seek(0)
    return buf


def to_csv(rows: list[dict]) -> BytesIO:
    import csv as csv_mod
    import io

    buf = io.StringIO()
    if rows:
        writer = csv_mod.DictWriter(buf, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    out = BytesIO(buf.getvalue().encode("utf-8"))
    out.seek(0)
    return out


def to_pdf(title: str, subtitle: str, rows: list[dict],
           summary: dict | None = None) -> BytesIO:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import (
        Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
    )

    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, title=title)
    styles = getSampleStyleSheet()
    story = [
        Paragraph(title, styles["Title"]),
        Paragraph(subtitle, styles["Normal"]),
        Spacer(1, 6 * mm),
    ]
    if summary:
        summary_line = " | ".join(f"{k}: {v}" for k, v in summary.items())
        story += [Paragraph(summary_line, styles["Heading2"]), Spacer(1, 4 * mm)]

    header = ["Date", "Student", "Register No", "Subject", "Period", "Status"]
    data = [header]
    for r in rows[:1000]:
        data.append([
            str(r.get("attendance_date", "")),
            str(r.get("student_name", "")),
            str(r.get("register_number") or "-"),
            str(r.get("subject_name", "")),
            str(r.get("period", "")),
            str(r.get("status", "")),
        ])
    if len(data) == 1:
        data.append(["-", "No records found", "-", "-", "-", "-"])

    table = Table(data, repeatRows=1, colWidths=[22 * mm, 48 * mm, 26 * mm,
                                                 42 * mm, 14 * mm, 20 * mm])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#4f46e5")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1),
         [colors.white, colors.HexColor("#f1f5f9")]),
    ]))
    story += [table,
              Spacer(1, 4 * mm),
              Paragraph(
                  f"Generated {date_cls.today().isoformat()} | rows: "
                  f"{min(len(rows), 1000)} of {len(rows)}",
                  styles["Normal"])]
    doc.build(story)
    buf.seek(0)
    return buf
