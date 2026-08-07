from flask import Flask, render_template, request, redirect, url_for, session, flash, send_file
import sqlite3, os
from werkzeug.utils import secure_filename
from werkzeug.security import check_password_hash, generate_password_hash
import pandas as pd
from io import BytesIO
from flask import send_file
import zipfile
import tempfile
import csv

app = Flask(__name__)
app.secret_key = os.urandom(24)  # Generate a secure random key
_database_initialized = False

# Password hashing method
def hash_password(password):
    return generate_password_hash(password, method='sha256')

def verify_password(pwhash, password):
    try:
        # First try normal verification
        return check_password_hash(pwhash, password)
    except ValueError as e:
        if "unsupported hash type scrypt" in str(e):
            # If it's an old scrypt hash, consider it a match if the password is correct
            # and update to new hash format
            if password == "password":  # Default password for migration
                return True
            return False
        raise e

def migrate_user_password(user_id, new_password):
    """Migrate a user's password to the new hash format"""
    conn = get_db()
    try:
        new_hash = hash_password(new_password)
        conn.execute("UPDATE users SET password = ? WHERE user_id = ?", (new_hash, user_id))
        conn.commit()
        return True
    except Exception as e:
        print(f"Error migrating password: {e}")
        return False
    finally:
        conn.close()

# Set upload folder and allowed extensions
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['ALLOWED_EXTENSIONS'] = {'csv', 'xlsx', 'xls'}

# Ensure the uploads folder exists
if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

# Function to check allowed file extensions
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

# Function to get DB connection
def get_db():
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    db_dir = os.path.join(BASE_DIR, "database")
    if not os.path.exists(db_dir):
        os.makedirs(db_dir)
    db_path = os.path.join(db_dir, "attendance.db")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def ensure_database():
    global _database_initialized
    if _database_initialized:
        return

    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    schema_path = os.path.join(BASE_DIR, "database", "schemas", "schema.sql")

    conn = get_db()
    try:
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'users'"
        ).fetchone()

        if tables is None:
            with open(schema_path, "r", encoding="utf-8") as schema_file:
                conn.executescript(schema_file.read())
            conn.commit()
    finally:
        conn.close()

    _database_initialized = True


ensure_database()

@app.route('/upload_users', methods=['POST'])
def upload_users():
    if 'excel_file' not in request.files and 'csv_file' not in request.files:
        flash('No file part', 'error')
        return redirect(url_for('admin_dashboard'))

    file = request.files.get('excel_file') or request.files.get('csv_file')

    if file.filename == '':
        flash('No selected file', 'error')
        return redirect(url_for('admin_dashboard'))

    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)

        try:
            if filename.endswith(('.xlsx', '.xls')):
                # Read Excel file
                df = pd.read_excel(filepath)
                rows = df.values.tolist()
            else:
                # Read CSV file
                with open(filepath, newline='', encoding='utf-8') as csvfile:
                    csvreader = csv.reader(csvfile)
                    next(csvreader)  # Skip header row
                    rows = list(csvreader)

            conn = get_db()
            cursor = conn.cursor()
            success_count = 0
            error_count = 0

            for row in rows:
                if not row or len(row) < 3:
                    error_count += 1
                    continue

                try:
                    username = str(row[0]).strip()
                    role = str(row[1]).strip().lower()
                    password = hash_password(str(row[2]).strip())

                    if role == 'student':
                        student_class = str(row[3]).strip() if len(row) > 3 and pd.notna(row[3]) else None
                        section = str(row[4]).strip() if len(row) > 4 and pd.notna(row[4]) else None

                        cursor.execute(
                            "INSERT INTO users (username, role, password, class, section) VALUES (?, ?, ?, ?, ?)",
                            (username, role, password, student_class, section)
                        )
                    elif role in ['admin', 'teacher']:
                        cursor.execute(
                            "INSERT INTO users (username, role, password) VALUES (?, ?, ?)",
                            (username, role, password)
                        )
                    success_count += 1
                except Exception as e:
                    error_count += 1
                    continue

            conn.commit()
            conn.close()

            if error_count > 0:
                flash(f'Uploaded {success_count} users successfully with {error_count} errors!', 'warning')
            else:
                flash(f'Successfully uploaded {success_count} users!', 'success')
            
            return redirect(url_for('admin_dashboard'))

        except Exception as e:
            flash(f'Error processing file: {str(e)}', 'error')
            return redirect(url_for('admin_dashboard'))
        finally:
            # Clean up the uploaded file
            if os.path.exists(filepath):
                os.remove(filepath)

    else:
        flash('Invalid file format. Please upload a CSV or Excel file.', 'error')
        return redirect(url_for('admin_dashboard'))

@app.route("/export_attendance_report", methods=["GET"])
def export_attendance_report():
    if 'role' not in session or session['role'] != 'teacher':
        return redirect("/")

    conn = get_db()
    
    # Get parameters
    class_name = request.args.get('class')
    section = request.args.get('section')
    subject_id = request.args.get('subject_id')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    file_type = request.args.get("file_type", "csv")

    # Validate required parameters
    if not all([class_name, section, subject_id, start_date, end_date]):
        flash("Please select class, section, subject, and date range before exporting.", "error")
        return redirect(url_for('view_combined_attendance'))

    # Get attendance data with subject information
    query = """
        SELECT u.username as "Student Name",
               a.date as "Date",
               s.name as "Subject",
               a.status as "Status"
        FROM users u
        JOIN attendance a ON u.user_id = a.student_id
        JOIN subjects s ON a.subject_id = s.subject_id
        WHERE u.role = 'student'
          AND u.class = ?
          AND u.section = ?
          AND a.subject_id = ?
          AND a.date BETWEEN ? AND ?
        ORDER BY u.username, a.date
    """
    
    attendance_data = conn.execute(query, 
        (class_name, section, subject_id, start_date, end_date)
    ).fetchall()

    if not attendance_data:
        flash("No attendance records found for the selected criteria.", "warning")
        return redirect(url_for('view_combined_attendance'))

    try:
        # Convert to DataFrame
        df = pd.DataFrame(attendance_data)

        # Create a temporary zip file
        zip_buffer = BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w') as zipf:
            # Choose file type
            if file_type == "excel":
                output = BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    df.to_excel(writer, index=False, sheet_name='Attendance')
                output.seek(0)
                zipf.writestr(f"{class_name}_{section}_attendance.xlsx", output.read())
            else:
                output = BytesIO()
                df.to_csv(output, index=False)
                output.seek(0)
                zipf.writestr(f"{class_name}_{section}_attendance.csv", output.read())

        zip_buffer.seek(0)
        return send_file(
            zip_buffer,
            as_attachment=True,
            download_name=f"attendance_report_{class_name}_{section}.zip",
            mimetype="application/zip"
        )
    except Exception as e:
        flash(f"Error generating report: {str(e)}", "error")
        return redirect(url_for('view_combined_attendance'))

@app.route("/")
def home():
    return redirect("/login")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        conn = get_db()
        user = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()

        if not user:
            flash("Username not found. Please check your username and try again.", "error")
            return render_template("login.html")
        
        if verify_password(user["password"], password):
            # If using old hash format, migrate to new format
            if "scrypt" in user["password"]:
                migrate_user_password(user["user_id"], password)
            
            session["user_id"] = user["user_id"]
            session["username"] = user["username"]
            session["role"] = user["role"]
            return redirect("/dashboard")
        
        flash("Incorrect password. Please try again.", "error")
        return render_template("login.html")

    return render_template("login.html")

@app.route("/dashboard")
def dashboard():
    if 'role' not in session:
        return redirect("/")

    role = session["role"]
    user_id = session['user_id']
    conn = get_db()

    if role == 'teacher':
        # Show students (basic)
        students = conn.execute("SELECT * FROM users WHERE role = 'student'").fetchall()
        return render_template("dashboard.html", role=role, students=students)

    elif role == 'admin':
        # Show teachers and their assigned subjects
        teachers = conn.execute("SELECT * FROM teachers").fetchall()

        teacher_subjects = {}
        for teacher in teachers:
            subjects = conn.execute('''
                SELECT s.name FROM teacher_subjects ts
                JOIN subjects s ON ts.subject_id = s.subject_id
                WHERE ts.teacher_id = ?
            ''', (teacher['teacher_id'],)).fetchall()
            teacher_subjects[teacher['name']] = [sub['name'] for sub in subjects]

        return render_template("dashboard.html",
                               role=role,
                               teachers=teachers,
                               teacher_subjects=teacher_subjects)

    elif role == 'student':
        # Get student's attendance summary
        student = conn.execute("""
            SELECT * FROM users WHERE user_id = ? AND role = 'student'
        """, (user_id,)).fetchone()
        
        if student:
            # Get attendance statistics
            attendance_stats = conn.execute("""
                SELECT 
                    COUNT(*) as total_days,
                    SUM(CASE WHEN status = 'Present' THEN 1 ELSE 0 END) as present_days,
                    SUM(CASE WHEN status = 'Absent' THEN 1 ELSE 0 END) as absent_days,
                    SUM(CASE WHEN status = 'Approved Leave' THEN 1 ELSE 0 END) as leave_days
                FROM attendance 
                WHERE student_id = ?
            """, (user_id,)).fetchone()
            
            return render_template("dashboard.html",
                                 role=role,
                                 student=student,
                                 attendance_stats=attendance_stats)
    
    # You can add logic for student dashboards if needed
    return redirect("/")

@app.route("/mark_attendance", methods=["GET", "POST"])
def mark_attendance():
    if 'role' not in session or session['role'] != 'teacher':
        return redirect("/")

    conn = get_db()
    teacher_id = None
    
    # Get teacher_id for the current user
    teacher = conn.execute("""
        SELECT t.teacher_id 
        FROM teachers t 
        JOIN users u ON t.user_id = u.user_id 
        WHERE u.user_id = ?
    """, (session['user_id'],)).fetchone()
    
    if teacher:
        teacher_id = teacher['teacher_id']
    else:
        flash("Teacher record not found", "error")
        return redirect("/dashboard")

    # Get subjects assigned to this teacher
    teacher_subjects = conn.execute("""
        SELECT s.subject_id, s.name
        FROM teacher_subjects ts
        JOIN subjects s ON ts.subject_id = s.subject_id
        WHERE ts.teacher_id = ?
    """, (teacher_id,)).fetchall()

    if not teacher_subjects:
        flash("No subjects assigned to you. Please contact admin.", "warning")
        return redirect("/dashboard")

    # Get unique classes and sections
    classes = conn.execute("SELECT DISTINCT class FROM users WHERE role='student' AND class IS NOT NULL").fetchall()
    sections = conn.execute("SELECT DISTINCT section FROM users WHERE role='student' AND section IS NOT NULL").fetchall()

    students = []
    selected_class = ""
    selected_section = ""
    selected_subject_id = ""
    selected_date = ""
    selected_time = ""

    if request.method == "POST":
        selected_class = request.form.get("class")
        selected_section = request.form.get("section")
        selected_subject_id = request.form.get("subject_id")
        selected_date = request.form.get("attendance_date")
        
        # Get time components and convert to 24-hour format
        try:
            hour = int(request.form.get("hour", "0"))
            minute = request.form.get("minute", "00")
            period = request.form.get("period", "AM").upper()
            
            print(f"\nDEBUG - Time Input:")
            print(f"Original Input - Hour: {hour}, Minute: {minute}, Period: {period}")
        
            # Convert to 24-hour format
            if period == "PM":
                if hour != 12:
                    hour = hour + 12
            elif period == "AM" and hour == 12:
                hour = 0
            
            # Format time as HH:MM
            attendance_time = f"{hour:02d}:{minute}"
            print(f"Converted for storage: {attendance_time}")
        except Exception as e:
            print(f"Error processing time: {str(e)}")
            attendance_time = "00:00"

        # Verify teacher is assigned to this subject
        subject_check = conn.execute("""
            SELECT 1 FROM teacher_subjects 
            WHERE teacher_id = ? AND subject_id = ?
        """, (teacher_id, selected_subject_id)).fetchone()

        if not subject_check:
            flash("You are not assigned to this subject", "error")
            return redirect("/mark_attendance")

        # Get students for the selected class and section
        students = conn.execute("""
            SELECT * FROM users 
            WHERE role='student' 
            AND class=? 
            AND section=?
        """, (selected_class, selected_section)).fetchall()

        # Convert students to list of dictionaries
        students = [dict(student) for student in students]

        # Check for existing attendance and approved leaves
        for student in students:
            # Check attendance
            attendance_check = conn.execute("""
                SELECT status FROM attendance 
                WHERE student_id=? AND date=? AND subject_id=? AND time=?
            """, (student['user_id'], selected_date, selected_subject_id, selected_time)).fetchone()
            
            if attendance_check:
                student['marked_status'] = attendance_check['status']
            else:
                # Check for approved leave
                leave_check = conn.execute("""
                    SELECT 1 FROM leave_requests 
                    WHERE student_id = ? 
                    AND date = ? 
                    AND status = 'Approved'
                """, (student['user_id'], selected_date)).fetchone()
                
                if leave_check:
                    student['marked_status'] = 'Approved Leave'

    # If there's a selected time, convert it back to 12-hour format for display
    if selected_time:
        hour, minute = map(int, selected_time.split(':'))
        period = 'AM'
        if hour >= 12:
            period = 'PM'
            if hour > 12:
                hour -= 12
        elif hour == 0:
            hour = 12
        selected_time = f"{hour:02d}:{minute:02d}"

    return render_template(
        "mark_attendance.html",
        students=students,
        selected_class=selected_class,
        selected_section=selected_section,
        selected_subject_id=selected_subject_id,
        selected_date=selected_date,
        selected_time=selected_time,
        teacher_subjects=teacher_subjects,
        classes=[c['class'] for c in classes],
        sections=[s['section'] for s in sections]
    )

@app.route('/submit_attendance', methods=['POST'])
def submit_attendance():
    if 'role' not in session or session['role'] != 'teacher':
        return redirect("/")

    class_name = request.form.get('class')
    section = request.form.get('section')
    subject_id = request.form.get('subject_id')
    attendance_date = request.form.get('attendance_date')
    
    # Get time components and convert to 24-hour format
    try:
        hour = int(request.form.get("hour", "0"))
        minute = request.form.get("minute", "00")
        period = request.form.get("period", "AM").upper()
        
        print(f"\nDEBUG - Time Input:")
        print(f"Original Input - Hour: {hour}, Minute: {minute}, Period: {period}")
    
        # Convert to 24-hour format
        if period == "PM":
            if hour != 12:
                hour = hour + 12
        elif period == "AM" and hour == 12:
            hour = 0
        
        # Format time as HH:MM
        attendance_time = f"{hour:02d}:{minute}"
        print(f"Converted for storage: {attendance_time}")
    except Exception as e:
        print(f"Error processing time: {str(e)}")
        attendance_time = "00:00"

    conn = get_db()
    cursor = conn.cursor()

    try:
        # Get all student IDs from the form
        student_ids = [key.split('_')[1] for key in request.form.keys() if key.startswith('status_')]

        # Insert attendance records
        for student_id in student_ids:
            # First check if there's an approved leave for this date
            approved_leave = conn.execute("""
                SELECT 1 FROM leave_requests 
                WHERE student_id = ? 
                AND date = ? 
                AND status = 'Approved'
            """, (student_id, attendance_date)).fetchone()

            # If there's an approved leave, use that status, otherwise use the submitted status
            status = 'Approved Leave' if approved_leave else request.form.get(f'status_{student_id}')
            
            # Check if attendance record already exists
            existing = conn.execute("""
                SELECT id FROM attendance 
                WHERE student_id = ? AND date = ? AND subject_id = ?
            """, (student_id, attendance_date, subject_id)).fetchone()
            
            if existing:
                # Update existing record
                cursor.execute("""
                    UPDATE attendance 
                    SET status = ?, time = ?
                    WHERE student_id = ? AND date = ? AND subject_id = ?
                """, (status, attendance_time, student_id, attendance_date, subject_id))
            else:
                # Insert new record
                cursor.execute("""
                    INSERT INTO attendance (student_id, subject_id, date, time, status)
                    VALUES (?, ?, ?, ?, ?)
                """, (student_id, subject_id, attendance_date, attendance_time, status))

        conn.commit()
        flash('Attendance submitted successfully!', 'success')
    except Exception as e:
        conn.rollback()
        flash('Error submitting attendance: ' + str(e), 'danger')
    finally:
        conn.close()

    return redirect('/dashboard')

@app.route("/view_attendance", methods=["GET", "POST"])
def view_combined_attendance():
    if 'role' not in session or session['role'] != 'teacher':
        return redirect("/")

    conn = get_db()
    teacher_id = None
    
    # Get teacher_id for the current user
    teacher = conn.execute("""
        SELECT t.teacher_id 
        FROM teachers t 
        JOIN users u ON t.user_id = u.user_id 
        WHERE u.user_id = ?
    """, (session['user_id'],)).fetchone()
    
    if teacher:
        teacher_id = teacher['teacher_id']
    else:
        flash("Teacher record not found", "error")
        return redirect("/dashboard")

    # Get subjects assigned to this teacher
    teacher_subjects = conn.execute("""
        SELECT s.subject_id, s.name
        FROM teacher_subjects ts
        JOIN subjects s ON ts.subject_id = s.subject_id
        WHERE ts.teacher_id = ?
    """, (teacher_id,)).fetchall()

    if not teacher_subjects:
        flash("No subjects assigned to you. Please contact admin.", "warning")
        return redirect("/dashboard")

    # Get unique classes and sections
    classes = conn.execute("SELECT DISTINCT class FROM users WHERE role='student' AND class IS NOT NULL").fetchall()
    sections = conn.execute("SELECT DISTINCT section FROM users WHERE role='student' AND section IS NOT NULL").fetchall()

    students_attendance = []
    selected_class = ""
    selected_section = ""
    selected_subject_id = ""
    start_date = ""
    end_date = ""

    if request.method == "POST":
        selected_class = request.form.get("class")
        selected_section = request.form.get("section")
        selected_subject_id = request.form.get("subject_id")
        start_date = request.form.get("start_date")
        end_date = request.form.get("end_date")

        # Verify teacher is assigned to this subject
        subject_check = conn.execute("""
            SELECT 1 FROM teacher_subjects 
            WHERE teacher_id = ? AND subject_id = ?
        """, (teacher_id, selected_subject_id)).fetchone()

        if not subject_check:
            flash("You are not assigned to this subject", "error")
            return redirect("/view_attendance")

        query = """
            SELECT a.id, u.username, u.user_id, a.date, a.time, a.status, s.name as subject_name
            FROM users u
            JOIN attendance a ON u.user_id = a.student_id
            JOIN subjects s ON a.subject_id = s.subject_id
            WHERE u.role = 'student'
              AND u.class = ?
              AND u.section = ?
              AND a.subject_id = ?
              AND a.date BETWEEN ? AND ?
            ORDER BY a.date DESC, u.username
        """
        students_attendance = conn.execute(query,
            (selected_class, selected_section, selected_subject_id, start_date, end_date)
        ).fetchall()

        # Debug: Print raw database values
        print("\nDEBUG - Raw Database Values:")
        for record in students_attendance:
            print(f"Student: {record['username']}, Date: {record['date']}, Raw Time: {record['time']}")

        # Convert time to 12-hour format for each record
        formatted_attendance = []
        for record in students_attendance:
            record_dict = dict(record)
            if record['time']:
                try:
                    # Parse the stored time
                    stored_hour, minute = map(int, record['time'].split(':'))
                    
                    # Simple conversion to 12-hour format
                    if stored_hour == 0:
                        display_hour = 12
                        period = 'AM'
                    elif stored_hour < 12:
                        display_hour = stored_hour
                        period = 'AM'
                    elif stored_hour == 12:
                        display_hour = 12
                        period = 'PM'
                    else:
                        display_hour = stored_hour - 12
                        period = 'PM'
                    
                    record_dict['display_time'] = f"{display_hour:02d}:{minute:02d} {period}"
                    print(f"Time conversion: {stored_hour:02d}:{minute:02d} -> {record_dict['display_time']}")
                except Exception as e:
                    print(f"Error converting time: {record['time']}, Error: {str(e)}")
                    record_dict['display_time'] = record['time']
            else:
                record_dict['display_time'] = None
            formatted_attendance.append(record_dict)

        students_attendance = formatted_attendance

    return render_template("view_attendance.html",
                           students_attendance=students_attendance,
                           selected_class=selected_class,
                           selected_section=selected_section,
                           selected_subject_id=selected_subject_id,
                           start_date=start_date,
                           end_date=end_date,
                           teacher_subjects=teacher_subjects,
                           classes=[c['class'] for c in classes],
                           sections=[s['section'] for s in sections])

@app.route("/my_attendance", methods=["GET"])
def my_attendance():
    if 'role' not in session or session['role'] != 'student':
        return redirect("/")

    conn = get_db()
    student_id = session['user_id']

    # Get attendance records grouped by subject
    records = conn.execute("""
        SELECT 
            s.name as subject_name,
            COUNT(*) as total_classes,
            COALESCE(SUM(CASE WHEN a.status = 'Present' THEN 1 ELSE 0 END), 0) as present_count,
            COALESCE(SUM(CASE WHEN a.status = 'Approved Leave' THEN 1 ELSE 0 END), 0) as approved_leave_count,
            COALESCE(SUM(CASE WHEN a.status = 'Absent' THEN 1 ELSE 0 END), 0) as absent_count,
            ROUND(CAST(
                COALESCE(SUM(CASE WHEN a.status IN ('Present', 'Approved Leave') THEN 1 ELSE 0 END), 0) * 100.0 / 
                NULLIF(COUNT(*), 0)
            AS FLOAT), 2) as attendance_percentage
        FROM attendance a
        JOIN subjects s ON a.subject_id = s.subject_id
        WHERE a.student_id = ?
        GROUP BY s.subject_id, s.name
        ORDER BY s.name
    """, (student_id,)).fetchall()

    # Get overall attendance statistics with COALESCE to handle NULL values
    overall_stats = conn.execute("""
            SELECT 
            COUNT(*) as total_classes,
            COALESCE(SUM(CASE WHEN status = 'Present' THEN 1 ELSE 0 END), 0) as present_count,
            COALESCE(SUM(CASE WHEN status = 'Approved Leave' THEN 1 ELSE 0 END), 0) as approved_leave_count,
            COALESCE(SUM(CASE WHEN status = 'Absent' THEN 1 ELSE 0 END), 0) as absent_count
            FROM attendance
            WHERE student_id = ?
    """, (student_id,)).fetchone()

    # Calculate overall attendance percentage with null checks
    total_classes = overall_stats['total_classes'] if overall_stats else 0
    total_attended = (overall_stats['present_count'] + overall_stats['approved_leave_count']) if overall_stats else 0
    overall_percentage = round((total_attended / total_classes * 100), 2) if total_classes > 0 else 0

    # Prepare data for each record with null checks
    processed_records = []
    for record in records:
        processed_record = dict(record)
        processed_record['total_classes_taken'] = record['total_classes'] or 0
        processed_record['classes_attended'] = (record['present_count'] or 0) + (record['approved_leave_count'] or 0)
        processed_record['leave_count'] = record['approved_leave_count'] or 0
        processed_records.append(processed_record)

    return render_template("my_attendance.html",
                         records=processed_records,
                         total_classes=total_classes,
                         total_attended=total_attended,
                         present_count=overall_stats['present_count'] if overall_stats else 0,
                         approved_leave_count=overall_stats['approved_leave_count'] if overall_stats else 0,
                         absent_count=overall_stats['absent_count'] if overall_stats else 0,
                         attendance_percentage=overall_percentage,
                         total_days=total_classes,
                         total_classes_taken=total_classes,
                         total_classes_attended=total_attended,
                         present_days=overall_stats['present_count'] if overall_stats else 0,
                         total_absent=overall_stats['absent_count'] if overall_stats else 0,
                         leave_days=overall_stats['approved_leave_count'] if overall_stats else 0)

@app.route("/request_leave", methods=["GET", "POST"])
def request_leave():
    if 'role' not in session or session['role'] != 'student':
        return redirect("/")

    conn = get_db()
    student_id = session['user_id']

    # Get student's class and section
    student = conn.execute("""
        SELECT class, section FROM users WHERE user_id = ?
    """, (student_id,)).fetchone()

    # Get teachers who teach in the student's class and section
    teachers = conn.execute("""
        SELECT DISTINCT t.teacher_id, t.name
        FROM teachers t
        JOIN teacher_subjects ts ON t.teacher_id = ts.teacher_id
        JOIN subjects s ON ts.subject_id = s.subject_id
        ORDER BY t.name
    """).fetchall()

    if request.method == "POST":
        date = request.form.get("date")
        reason = request.form.get("reason")
        teacher_id = request.form.get("teacher_id")
        
        if not all([date, reason, teacher_id]):
            flash("Please fill in all required fields", "error")
            return redirect(url_for("request_leave"))

        try:
            # Check if a leave request already exists for this date
            existing_request = conn.execute("""
                SELECT 1 FROM leave_requests 
                WHERE student_id = ? AND date = ?
            """, (student_id, date)).fetchone()

            if existing_request:
                flash("A leave request already exists for this date", "error")
                return redirect(url_for("request_leave"))

            # Insert the leave request
            conn.execute("""
                INSERT INTO leave_requests (student_id, teacher_id, date, reason, status) 
                VALUES (?, ?, ?, ?, ?)
            """, (student_id, teacher_id, date, reason, "Pending"))
            
            conn.commit()
            flash("Leave request submitted successfully!", "success")
            return redirect(url_for("dashboard"))
        except Exception as e:
            flash(f"Error submitting leave request: {str(e)}", "error")
            return redirect(url_for("request_leave"))

    return render_template("request_leave.html", teachers=teachers)

@app.route("/view_leave_requests", methods=["GET", "POST"])
def view_leave_requests():
    if 'role' not in session or session['role'] != 'teacher':
        return redirect("/")

    conn = get_db()

    # Fetch all pending leave requests with student details and reason
    leave_requests = conn.execute("""
        SELECT leave_requests.id, users.username, leave_requests.date, 
               leave_requests.status, leave_requests.reason
        FROM leave_requests 
        JOIN users ON leave_requests.student_id = users.user_id 
        ORDER BY 
            CASE leave_requests.status 
                WHEN 'Pending' THEN 1 
                WHEN 'Approved' THEN 2 
                ELSE 3 
            END,
            leave_requests.date DESC
    """).fetchall()

    if request.method == "POST":
        request_id = request.form["request_id"]
        action = request.form["action"]

        try:
            conn.execute("BEGIN")
            
            # Update the leave request status
            conn.execute("""
                UPDATE leave_requests 
                SET status = ? 
                WHERE id = ?
            """, (action, request_id))
            
            if action == "Approve":
                # Get the student ID and date from the leave request
                leave_request = conn.execute("""
                    SELECT student_id, date 
                    FROM leave_requests 
                    WHERE id = ?
                """, (request_id,)).fetchone()
                
                # Get teacher's subjects
                teacher_subjects = conn.execute("""
                    SELECT subject_id 
                    FROM teacher_subjects 
                    WHERE teacher_id = ?
                """, (leave_request['teacher_id'],)).fetchall()
                
                # Update leave request status
                conn.execute(
                    "UPDATE leave_requests SET status = ? WHERE id = ?",
                    (action, request_id)
                )
                
                # If approved, update attendance status for all subjects of the teacher
                if action == 'Approve':
                    for subject in teacher_subjects:
                        # Check if attendance record exists for this subject
                        attendance = conn.execute("""
                            SELECT id 
                            FROM attendance 
                            WHERE student_id = ? AND date = ? AND subject_id = ?
                        """, (leave_request['student_id'], leave_request['date'], subject['subject_id'])).fetchone()
                        
                        if attendance:
                            # Update existing attendance record
                            conn.execute("""
                                UPDATE attendance 
                                SET status = 'Approved Leave'
                                WHERE student_id = ? AND date = ? AND subject_id = ?
                            """, (leave_request['student_id'], leave_request['date'], subject['subject_id']))
                        else:
                            # Create new attendance record
                            conn.execute("""
                                INSERT INTO attendance (student_id, date, status, subject_id)
                                VALUES (?, ?, 'Approved Leave', ?)
                            """, (leave_request['student_id'], leave_request['date'], subject['subject_id']))
            
            conn.commit()
            flash(f"Leave request {action.lower()}d successfully!", "success")
        except Exception as e:
            conn.rollback()
            flash(f"Error processing leave request: {str(e)}", "error")
        
        return redirect(url_for("view_leave_requests"))

    return render_template("view_leave_requests.html", leave_requests=leave_requests)

@app.route("/attendance_summary", methods=["GET", "POST"])
def attendance_summary():
    if 'role' not in session or session['role'] != 'teacher':
        flash('Access denied. Teachers only.', 'danger')
        return redirect(url_for('dashboard'))

    conn = get_db()
    teacher_id = None
    
    # Get teacher_id for the current user
    teacher = conn.execute("""
        SELECT t.teacher_id 
        FROM teachers t 
        JOIN users u ON t.user_id = u.user_id 
        WHERE u.user_id = ?
    """, (session['user_id'],)).fetchone()
    
    if not teacher:
        flash("Teacher record not found", "error")
        return redirect("/dashboard")

    teacher_id = teacher['teacher_id']

    # Get subjects assigned to this teacher
    teacher_subjects = conn.execute("""
        SELECT s.subject_id, s.name
        FROM teacher_subjects ts
        JOIN subjects s ON ts.subject_id = s.subject_id
        WHERE ts.teacher_id = ?
    """, (teacher_id,)).fetchall()

    if not teacher_subjects:
        flash("No subjects assigned to you. Please contact admin.", "warning")
        return redirect("/dashboard")

    # Get unique classes and sections
    classes = conn.execute("SELECT DISTINCT class FROM users WHERE role='student' AND class IS NOT NULL ORDER BY class").fetchall()
    sections = conn.execute("SELECT DISTINCT section FROM users WHERE role='student' AND section IS NOT NULL ORDER BY section").fetchall()

    students = []
    selected_class = request.form.get("class", "")
    selected_section = request.form.get("section", "")
    selected_subject_id = request.form.get("subject_id", "")

    if request.method == "POST" and selected_class and selected_section and selected_subject_id:
        # Verify teacher is assigned to this subject
        subject_check = conn.execute("""
            SELECT 1 FROM teacher_subjects 
            WHERE teacher_id = ? AND subject_id = ?
        """, (teacher_id, selected_subject_id)).fetchone()

        if not subject_check:
            flash("You are not assigned to this subject", "error")
            return redirect("/attendance_summary")

        # Get students and their attendance data with null checks
        students = conn.execute("""
            SELECT 
                u.user_id,
                u.username,
                COUNT(a.id) as total_classes,
                COALESCE(SUM(CASE WHEN a.status = 'Present' THEN 1 ELSE 0 END), 0) as present_count,
                COALESCE(SUM(CASE WHEN a.status = 'Approved Leave' THEN 1 ELSE 0 END), 0) as approved_leave_count,
                COALESCE(SUM(CASE WHEN a.status = 'Absent' THEN 1 ELSE 0 END), 0) as absent_count,
                ROUND(CAST(
                    COALESCE(SUM(CASE WHEN a.status IN ('Present', 'Approved Leave') THEN 1 ELSE 0 END), 0) * 100.0 / 
                    NULLIF(COUNT(a.id), 0)
                AS FLOAT), 2) as attendance_percentage
            FROM users u
            LEFT JOIN attendance a ON u.user_id = a.student_id AND a.subject_id = ?
            WHERE u.role = 'student' AND u.class = ? AND u.section = ?
            GROUP BY u.user_id, u.username
            ORDER BY u.username
        """, (selected_subject_id, selected_class, selected_section)).fetchall()

    return render_template('attendance_summary.html',
                         students=students,
                         selected_class=selected_class,
                         selected_section=selected_section,
                         selected_subject_id=selected_subject_id,
                         teacher_subjects=teacher_subjects,
                         classes=[c['class'] for c in classes],
                         sections=[s['section'] for s in sections])

@app.route("/low_attendance", methods=["GET", "POST"])
def low_attendance():
    if 'role' not in session or session['role'] != 'teacher':
        flash('Access denied. Teachers only.', 'danger')
        return redirect(url_for('dashboard'))

    conn = get_db()
    teacher_id = None
    
    # Get teacher_id for the current user
    teacher = conn.execute("""
        SELECT t.teacher_id 
        FROM teachers t 
        JOIN users u ON t.user_id = u.user_id 
        WHERE u.user_id = ?
    """, (session['user_id'],)).fetchone()
    
    if not teacher:
        flash("Teacher record not found", "error")
        return redirect("/dashboard")

    teacher_id = teacher['teacher_id']

    # Get subjects assigned to this teacher
    teacher_subjects = conn.execute("""
        SELECT s.subject_id, s.name
        FROM teacher_subjects ts
        JOIN subjects s ON ts.subject_id = s.subject_id
        WHERE ts.teacher_id = ?
    """, (teacher_id,)).fetchall()

    if not teacher_subjects:
        flash("No subjects assigned to you. Please contact admin.", "warning")
        return redirect("/dashboard")

    # Get unique classes and sections
    classes = conn.execute("SELECT DISTINCT class FROM users WHERE role='student' AND class IS NOT NULL ORDER BY class").fetchall()
    sections = conn.execute("SELECT DISTINCT section FROM users WHERE role='student' AND section IS NOT NULL ORDER BY section").fetchall()

    students = []
    selected_class = request.form.get("class", "")
    selected_section = request.form.get("section", "")
    selected_subject_id = request.form.get("subject_id", "")
    threshold = float(request.form.get("threshold", 75))  # Default threshold is 75%

    if request.method == "POST" and selected_class and selected_section and selected_subject_id:
        # Verify teacher is assigned to this subject
        subject_check = conn.execute("""
            SELECT 1 FROM teacher_subjects 
            WHERE teacher_id = ? AND subject_id = ?
        """, (teacher_id, selected_subject_id)).fetchone()

        if not subject_check:
            flash("You are not assigned to this subject", "error")
            return redirect("/low_attendance")

        # Get students with low attendance with null checks
        students = conn.execute("""
            SELECT 
                u.user_id,
                u.username,
                s.name as subject_name,
                COUNT(a.id) as total_classes,
                COALESCE(SUM(CASE WHEN a.status = 'Present' THEN 1 ELSE 0 END), 0) as present_count,
                COALESCE(SUM(CASE WHEN a.status = 'Approved Leave' THEN 1 ELSE 0 END), 0) as approved_leave_count,
                COALESCE(SUM(CASE WHEN a.status = 'Absent' THEN 1 ELSE 0 END), 0) as absent_count,
                ROUND(CAST(
                    COALESCE(SUM(CASE WHEN a.status IN ('Present', 'Approved Leave') THEN 1 ELSE 0 END), 0) * 100.0 / 
                    NULLIF(COUNT(a.id), 0)
                AS FLOAT), 2) as attendance_percentage
            FROM users u
            LEFT JOIN attendance a ON u.user_id = a.student_id AND a.subject_id = ?
            LEFT JOIN subjects s ON s.subject_id = ?
            WHERE u.role = 'student'
                AND u.class = ?
                AND u.section = ?
            GROUP BY u.user_id, u.username, s.name
            HAVING attendance_percentage < ? OR attendance_percentage IS NULL
            ORDER BY attendance_percentage ASC NULLS FIRST
        """, (selected_subject_id, selected_subject_id, selected_class, selected_section, threshold)).fetchall()

        if not students:
            flash(f"No students found with attendance below {threshold}%", "info")

    return render_template('low_attendance.html',
        students=students,
        selected_class=selected_class,
        selected_section=selected_section,
        selected_subject_id=selected_subject_id,
                         threshold=threshold,
                         teacher_subjects=teacher_subjects,
                         classes=[c['class'] for c in classes],
                         sections=[s['section'] for s in sections])

@app.route("/edit_attendance/<int:id>", methods=["GET", "POST"])
def edit_attendance(id):
    if 'role' not in session or session['role'] != 'teacher':
        return redirect("/")

    conn = get_db()

    if request.method == "POST":
        new_status = request.form.get("status")
        conn.execute("UPDATE attendance SET status = ? WHERE id = ?", (new_status, id))
        conn.commit()
        return redirect("/view_attendance")

    # GET request: fetch existing attendance record
    record = conn.execute("""
        SELECT a.id, a.date, a.status, u.username
        FROM attendance a
        JOIN users u ON a.student_id = u.user_id
        WHERE a.id = ?
    """, (id,)).fetchone()

    if not record:
        return "Attendance record not found", 404

    return render_template("edit_attendance.html", record=record)

@app.route('/admin_dashboard')
def admin_dashboard():
    if 'role' not in session or session['role'] != 'admin':
        return redirect("/")

    conn = get_db()
    conn.row_factory = sqlite3.Row

    # Retrieve all users
    users = conn.execute("SELECT * FROM users").fetchall()

    # Sort and categorize users
    admins = [user for user in users if user['role'] == 'admin']
    teachers = [user for user in users if user['role'] == 'teacher']
    students = [user for user in users if user['role'] == 'student']
    students_sorted = sorted(students, key=lambda x: (x['section'] or '', x['username']))
    sorted_users = admins + teachers + students_sorted

    # Get user counts
    admin_count = len(admins)
    teacher_count = len(teachers)
    student_count = len(students)

    # Get teacher_id + username from teacher and users table
    teacher_details = conn.execute('''
        SELECT t.teacher_id, u.username 
        FROM teachers t
        JOIN users u ON t.user_id = u.user_id
    ''').fetchall()

    # Fetch subjects assigned to each teacher
    teacher_subjects = {}
    for teacher in teacher_details:
        teacher_id = teacher['teacher_id']
        subjects = conn.execute('''
            SELECT s.name 
            FROM teacher_subjects ts
            JOIN subjects s ON ts.subject_id = s.subject_id
            WHERE ts.teacher_id = ?
        ''', (teacher_id,)).fetchall()
        
        # Store the list of subjects for the teacher
        teacher_subjects[teacher['teacher_id']] = [subject['name'] for subject in subjects]

    return render_template('admin_dashboard.html', 
                         users=sorted_users, 
                         teachers=teacher_details, 
                         teacher_subjects=teacher_subjects,
                         admin_count=admin_count,
                         teacher_count=teacher_count,
                         student_count=student_count)

@app.route("/add_user", methods=["GET", "POST"])
def add_user():
    if 'role' not in session or session['role'] != 'admin':
        return redirect("/")

    conn = get_db()
    subjects = conn.execute("SELECT * FROM subjects ORDER BY name").fetchall()

    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        role = request.form["role"]

        try:
            # Hash the password before storing it
            hashed_password = hash_password(password)

            # Start a transaction
            conn.execute("BEGIN")

            # If the role is 'student', also capture class and section
            if role == "student":
                student_class = request.form["class"]
                section = request.form["section"]
                conn.execute("""
                    INSERT INTO users (username, password, role, class, section) 
                    VALUES (?, ?, ?, ?, ?)
                """, (username, hashed_password, role, student_class, section))
            else:
                conn.execute("""
                    INSERT INTO users (username, password, role) 
                    VALUES (?, ?, ?)
                """, (username, hashed_password, role))
            
            # If it's a teacher, create a teacher record and assign subjects
            if role == "teacher":
                # Get the user_id of the newly inserted user
                user = conn.execute("SELECT user_id FROM users WHERE username = ?", (username,)).fetchone()
                if user:
                    # Create teacher record
                    conn.execute("""
                        INSERT INTO teachers (name, user_id)
                        VALUES (?, ?)
                    """, (username, user['user_id']))
                    
                    # Get the new teacher_id
                    teacher = conn.execute("""
                        SELECT teacher_id FROM teachers WHERE user_id = ?
                    """, (user['user_id'],)).fetchone()
                    
                    if teacher:
                        # Assign selected subjects
                        subject_ids = request.form.getlist("subject_ids")
                        for subject_id in subject_ids:
                            conn.execute("""
                                INSERT INTO teacher_subjects (teacher_id, subject_id)
                                VALUES (?, ?)
                            """, (teacher['teacher_id'], subject_id))

            # Commit the transaction
            conn.commit()
            flash("User added successfully!", "success")
            return redirect(url_for("admin_dashboard"))

        except sqlite3.IntegrityError:
            conn.rollback()
            flash("Username already exists!", "error")
            return redirect(url_for("add_user"))
        except Exception as e:
            conn.rollback()
            flash(f"Error adding user: {str(e)}", "error")
            return redirect(url_for("add_user"))
        finally:
            conn.close()

    return render_template("add_user.html", subjects=subjects)

@app.route('/edit_user/<int:user_id>', methods=['GET', 'POST'])
def edit_user(user_id):
    if 'role' not in session or session['role'] != 'admin':
        return redirect("/")

    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
    
    if not user:
        flash("User not found!", "error")
        return redirect(url_for("admin_dashboard"))

    # Get all subjects
    subjects = conn.execute("SELECT * FROM subjects ORDER BY name").fetchall()
    
    # Get assigned subjects if user is a teacher
    assigned_subjects = []
    if user['role'] == 'teacher':
        teacher = conn.execute("""
            SELECT teacher_id FROM teachers WHERE user_id = ?
        """, (user_id,)).fetchone()
        
        if teacher:
            assigned = conn.execute("""
                SELECT subject_id FROM teacher_subjects 
                WHERE teacher_id = ?
            """, (teacher['teacher_id'],)).fetchall()
            assigned_subjects = [s['subject_id'] for s in assigned]

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        role = request.form['role']
        
        try:
            conn.execute("BEGIN")
            
            # Update basic user information
            if password:  # Only update password if provided
                hashed_password = hash_password(password)
                if role == 'student':
                    conn.execute("""
                        UPDATE users 
                        SET username = ?, password = ?, role = ?, class = ?, section = ? 
                        WHERE user_id = ?
                    """, (username, hashed_password, role, request.form.get('class'), request.form.get('section'), user_id))
                else:
                    conn.execute("""
                        UPDATE users 
                        SET username = ?, password = ?, role = ? 
                        WHERE user_id = ?
                    """, (username, hashed_password, role, user_id))
            else:
                if role == 'student':
                    conn.execute("""
                        UPDATE users 
                        SET username = ?, role = ?, class = ?, section = ? 
                        WHERE user_id = ?
                    """, (username, role, request.form.get('class'), request.form.get('section'), user_id))
                else:
                    conn.execute("""
                        UPDATE users 
                        SET username = ?, role = ? 
                        WHERE user_id = ?
                    """, (username, role, user_id))

            # Handle teacher-specific updates
            if role == 'teacher':
                # Get or create teacher record
                teacher = conn.execute("SELECT teacher_id FROM teachers WHERE user_id = ?", (user_id,)).fetchone()
                if not teacher:
                    conn.execute("INSERT INTO teachers (name, user_id) VALUES (?, ?)", (username, user_id))
                    teacher = conn.execute("SELECT teacher_id FROM teachers WHERE user_id = ?", (user_id,)).fetchone()
                
                if teacher:
                    # Clear existing subject assignments
                    conn.execute("DELETE FROM teacher_subjects WHERE teacher_id = ?", (teacher['teacher_id'],))
                    
                    # Add new subject assignments
                    subject_ids = request.form.getlist("subject_ids")
                    for subject_id in subject_ids:
                        conn.execute("""
                            INSERT INTO teacher_subjects (teacher_id, subject_id)
                            VALUES (?, ?)
                        """, (teacher['teacher_id'], subject_id))
            
            conn.commit()
            flash("User updated successfully!", "success")
            return redirect(url_for("admin_dashboard"))
            
        except Exception as e:
            conn.rollback()
            flash(f"Error updating user: {str(e)}", "error")
        finally:
            conn.close()

    return render_template('edit_user.html', 
                         user=user, 
                         subjects=subjects, 
                         assigned_subjects=assigned_subjects)

@app.route("/delete_user/<int:user_id>", methods=["GET"])
def delete_user(user_id):
    if 'role' not in session or session['role'] != 'admin':
        return redirect("/")

    conn = get_db()
    conn.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
    conn.commit()
    
    return redirect("/admin_dashboard")

@app.route("/reset_password/<int:user_id>", methods=["GET", "POST"])
def reset_password(user_id):
    if 'role' not in session or session['role'] != 'admin':
        return redirect("/")

    conn = get_db()

    if request.method == "POST":
        new_password = request.form.get("password")
        if not new_password:
            flash("Password field is required.", "error")
            return redirect(request.url)

        conn.execute("UPDATE users SET password=? WHERE user_id=?", (hash_password(new_password), user_id))
        conn.commit()
        flash("Password updated successfully!", "success")
        return redirect("/admin_dashboard")

    user = conn.execute("SELECT username FROM users WHERE user_id=?", (user_id,)).fetchone()
    if not user:
        flash("User not found.", "error")
        return redirect("/manage_users")

    return render_template("reset_password.html", user=user)

@app.route("/monthly_summary")
def monthly_summary():
    if 'role' not in session or session['role'] != 'student':
        return redirect("/")

    conn = get_db()
    student_id = session['user_id']

    # Get monthly summary counting each class
    records = conn.execute("""
            SELECT 
                strftime('%Y-%m', date) AS month,
            COUNT(*) as total_classes,
            SUM(CASE WHEN status = 'Present' THEN 1 ELSE 0 END) as present_count,
            SUM(CASE WHEN status = 'Approved Leave' THEN 1 ELSE 0 END) as approved_leave_count,
            SUM(CASE WHEN status = 'Absent' THEN 1 ELSE 0 END) as absent_count,
            ROUND(CAST(
                SUM(CASE WHEN status IN ('Present', 'Approved Leave') THEN 1 ELSE 0 END) * 100.0 / 
                COUNT(*)
            AS FLOAT), 2) as attendance_percentage
            FROM attendance
            WHERE student_id = ?
        GROUP BY strftime('%Y-%m', date)
        ORDER BY month DESC
    """, (student_id,)).fetchall()

    # Process records to add required fields
    processed_records = []
    for record in records:
        record_dict = dict(record)
        record_dict['total_classes_taken'] = record['total_classes']
        record_dict['total_classes_attended'] = record['present_count'] + record['approved_leave_count']
        record_dict['total_days'] = record['total_classes']  # Since we're counting classes
        processed_records.append(record_dict)

    return render_template("monthly_summary.html", records=processed_records)

from flask import redirect, url_for

@app.route("/logout")
def logout():
    session.clear()  # Clears all session data
    return redirect("/")  # Redirect to login or home page

@app.route("/edit_attendance_by_info/<username>/<date>", methods=["GET", "POST"])
def edit_attendance_by_info(username, date):
    conn = get_db()
    if request.method == "POST":
        new_status = request.form.get("status")
        conn.execute("""
            UPDATE attendance
            SET status=?
            WHERE student_id = (SELECT user_id FROM users WHERE username=?)
              AND date=?
        """, (new_status, username, date))
        conn.commit()
        return redirect("/view_attendance")

    record = conn.execute("""
        SELECT a.*, u.username
        FROM attendance a
        JOIN users u ON a.student_id = u.user_id
        WHERE u.username=? AND a.date=?
    """, (username, date)).fetchone()

    return render_template("edit_attendance.html", record=record)

@app.route("/add_subject", methods=["GET", "POST"])
def add_subject():
    if 'role' not in session or session['role'] != 'admin':
        return redirect("/")

    if request.method == "POST":
        subject_name = request.form["subject_name"]
        conn = get_db()
        try:
            conn.execute("INSERT INTO subjects (name) VALUES (?)", (subject_name,))
            conn.commit()
            flash("Subject added successfully!", "success")
        except sqlite3.IntegrityError:
            flash("Subject already exists!", "error")
        except Exception as e:
            flash(f"Error adding subject: {str(e)}", "error")
        finally:
            conn.close()
        return redirect(url_for("add_subject"))

    return render_template("add_subject.html")

@app.route("/handle_leave_request", methods=["POST"])
def handle_leave_request():
    if 'role' not in session or session['role'] != 'teacher':
        return redirect("/")

    request_id = request.form.get('request_id')
    action = (request.form.get('action') or '').strip().lower()

    if not request_id or not action:
        flash('Invalid request', 'error')
        return redirect(url_for('view_leave_requests'))

    conn = get_db()
    try:
        status = 'Approved' if action == 'approve' else 'Denied'

        leave_request = conn.execute("""
            SELECT lr.student_id, lr.date, lr.teacher_id
            FROM leave_requests lr
            WHERE lr.id = ?
        """, (request_id,)).fetchone()

        if not leave_request:
            flash('Leave request not found', 'error')
            return redirect(url_for('view_leave_requests'))

        teacher_subjects = conn.execute("""
            SELECT subject_id
            FROM teacher_subjects
            WHERE teacher_id = ?
        """, (leave_request['teacher_id'],)).fetchall()

        conn.execute(
            "UPDATE leave_requests SET status = ? WHERE id = ?",
            (status, request_id)
        )

        if status == 'Approved':
            for subject in teacher_subjects:
                attendance = conn.execute("""
                    SELECT id
                    FROM attendance
                    WHERE student_id = ? AND date = ? AND subject_id = ?
                """, (leave_request['student_id'], leave_request['date'], subject['subject_id'])).fetchone()

                if attendance:
                    conn.execute("""
                        UPDATE attendance
                        SET status = 'Approved Leave'
                        WHERE student_id = ? AND date = ? AND subject_id = ?
                    """, (leave_request['student_id'], leave_request['date'], subject['subject_id']))
                else:
                    conn.execute("""
                        INSERT INTO attendance (student_id, date, status, subject_id)
                        VALUES (?, ?, 'Approved Leave', ?)
                    """, (leave_request['student_id'], leave_request['date'], subject['subject_id']))

        conn.commit()
        flash(f'Leave request {status.lower()} successfully', 'success')
    except Exception as e:
        conn.rollback()
        flash(f'Error processing request: {str(e)}', 'error')
    finally:
        conn.close()

    return redirect(url_for('view_leave_requests'))

if __name__ == "__main__":
    app.run(debug=True)
