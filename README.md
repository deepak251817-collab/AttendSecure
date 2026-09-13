# Attendance Management System

A role-based web application for managing student attendance, teacher-subject assignments, leave requests, reports, and attendance analytics.

## Team

| Member | Role |
|---|---|
| Deepak R | Developer |
| Yashaswini M | Developer |

## What the project does

The system supports three roles:

- **Admin:** manage users, teachers, subjects, assignments, passwords, and bulk imports.
- **Teacher:** mark attendance, edit attendance, review attendance summaries, identify low-attendance students, process leave requests, and export reports.
- **Student:** view personal attendance, monthly summaries, attendance percentage, and submit leave requests.

## Key Features

### Authentication and security
- Password hashing with Werkzeug PBKDF2-SHA256.
- Session-based role access control.
- Stable application secret generated locally and stored in the ignored `.flask_secret_key` file, or supplied through `FLASK_SECRET_KEY`.
- HTTP-only and SameSite session cookies.
- Upload size limit and restricted CSV/Excel upload extensions.
- SQLite foreign-key enforcement.
- Sensitive/runtime files excluded from Git.

### Attendance management
- Mark attendance by class, section, subject, date, and time.
- Present, Absent, and Approved Leave states.
- Prevent duplicate attendance for the same student, subject, and date.
- Teacher attendance history and editing.
- Student attendance by subject and overall percentage.
- Monthly attendance summaries.
- Low-attendance monitoring.

### Leave management
- Student leave request submission.
- Teacher-specific leave request visibility.
- Approve/deny workflow.
- Approved leave automatically updates attendance for the teacher's assigned subjects.

### Administration
- User creation, editing, deletion, and password reset.
- Subject management.
- Teacher-subject assignment management.
- CSV/XLS/XLSX bulk user import.
- CSV/Excel attendance export.

### Project quality improvements
- Health endpoint at `/health` for quick service checks.
- Smoke tests in `tests/test_smoke.py`.
- Environment-based configuration through `.env.example` / shell variables.
- Clean source-only repository structure without `.git`, `.venv`, database dumps, or generated cache files.

## Technology Stack

- **Backend:** Python 3.11+, Flask
- **Frontend:** HTML, Jinja2, Bootstrap/CDN assets already used by the templates
- **Database:** SQLite
- **Data processing:** pandas, openpyxl
- **Authentication:** Werkzeug password hashing and Flask sessions
- **Optional migration:** MySQL via `mysql-connector-python`

## Project Structure

```text
Attendance_System-Project/
├── app.py
├── reset_db.py
├── check_users.py
├── migrate_to_mysql.py
├── requirements.txt
├── requirements-dev.txt
├── .env.example
├── .gitignore
├── sample_users.csv.example
├── database/
│   ├── db_manager.py
│   └── schemas/
│       └── schema.sql
├── templates/
│   ├── base.html
│   ├── login.html
│   ├── dashboard.html
│   ├── mark_attendance.html
│   ├── attendance_summary.html
│   ├── low_attendance.html
│   ├── my_attendance.html
│   ├── monthly_summary.html
│   ├── request_leave.html
│   ├── view_leave_requests.html
│   ├── add_user.html
│   ├── edit_user.html
│   ├── add_subject.html
│   ├── assign_subject.html
│   └── ...
├── tests/
│   └── test_smoke.py
├── docs/
│   └── (project documentation can be kept here)
└── uploads/
    └── .gitkeep
```

## Run the project locally

### 1. Clone / extract the project

```bash
git clone <your-repository-url>
cd Attendance_System-Project
```

### 2. Create a virtual environment

**Windows PowerShell:**

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

**Windows CMD:**

```cmd
python -m venv .venv
.venv\Scripts\activate
```

**Linux/macOS:**

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install dependencies

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

For development/testing:

```bash
pip install -r requirements-dev.txt
```

### 4. Initialize the database

The repository intentionally does **not** contain `database/attendance.db`.

Run:

```bash
python reset_db.py
```

You will be asked to set the admin password. Press Enter to generate a strong random password, or provide your own password. For an unattended local setup, you can use an environment variable.

**PowerShell:**

```powershell
$env:ADMIN_PASSWORD="YourStrongPassword"
python reset_db.py
```

**CMD:**

```cmd
set ADMIN_PASSWORD=YourStrongPassword
python reset_db.py
```

### 5. Start the application

```bash
python app.py
```

Open:

```text
http://127.0.0.1:5000
```

Health check:

```text
http://127.0.0.1:5000/health
```

### Alternative Flask command

```bash
flask --app app run
```

For development debugging:

**PowerShell:**

```powershell
$env:FLASK_DEBUG="1"
python app.py
```

## Environment configuration

Copy `.env.example` to `.env` for your own reference, or set variables in the shell. The application intentionally does not load `.env` automatically, so production deployments should use their platform's environment-variable mechanism.

Important variables:

```text
FLASK_SECRET_KEY=...
FLASK_DEBUG=0
FLASK_HOST=127.0.0.1
PORT=5000
ATTENDANCE_DB_PATH=...
ADMIN_PASSWORD=...
```

Never commit `.env`, database files, uploaded files, private keys, or generated secrets.

## Bulk user import

Use `sample_users.csv.example` as the column-format reference:

```csv
Username,Role,Password,Class,Section
teacher01,teacher,CHANGE_ME,,
student01,student,CHANGE_ME,AIML,A
student02,student,CHANGE_ME,AIML,A
```

Do not put real passwords or personal data into files that will be committed to Git.

## Useful maintenance commands

List database users:

```bash
python check_users.py
```

Reset the local database:

```bash
python reset_db.py
```

Run smoke tests:

```bash
pytest -q
```

## Git and security rules

The `.gitignore` is configured to exclude:

- `.venv/`, caches, compiled Python files
- `.env` and other local environment files
- `.flask_secret_key`
- SQLite/database files (`*.db`, `*.sqlite`, `*.sqlite3`)
- uploaded files and logs
- private certificates/keys
- IDE files and OS junk
- generated ZIP/build artifacts

If a secret was committed in an earlier Git history, adding it to `.gitignore` is **not enough**. Rotate the secret/password and remove the sensitive data from Git history before publishing the repository.

## Optional MySQL migration

`migrate_to_mysql.py` is kept as an optional migration utility. It is not required to run the Flask application.

Install its extra dependency only when needed:

```bash
pip install mysql-connector-python
python migrate_to_mysql.py
```

Review the migration script and database credentials before using it on real data.

## Recommended next-level features

For a stronger final-year / portfolio project, the next improvements should be:

1. **QR-code attendance:** teacher generates a short-lived QR code and students scan it.
2. **Dashboard analytics:** charts for attendance trends, subject-wise performance, and class-level statistics.
3. **Timetable support:** attendance sessions can be tied to scheduled periods.
4. **Audit log:** track who created, changed, approved, or deleted attendance records.
5. **Email notifications:** notify students when attendance drops below a threshold or leave is approved/denied.
6. **Stronger security:** add CSRF protection, rate limiting, account lockout, and production HTTPS configuration.
7. **Deployment:** Docker + PostgreSQL/MySQL + production WSGI server such as Gunicorn/waitress.
8. **Role permissions:** move from simple roles to explicit permissions for larger institutions.

## Team Git workflow

Use feature branches rather than committing directly to `main`:

```bash
git checkout -b feature/qr-attendance
git add .
git commit -m "feat: add QR attendance workflow"
git push -u origin feature/qr-attendance
```

Then create a Pull Request and review changes before merging.

## Important note

This repository is now intended to contain **source code and project configuration only**. Local databases, credentials, virtual environments, uploaded files, Git metadata, and other runtime artifacts should remain outside the committed source tree.
