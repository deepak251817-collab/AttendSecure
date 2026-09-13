# Attendance Management System

A role-based college attendance management system built with **Flask 3 + MySQL 8**, featuring attendance tracking, leave workflows, QR-code check-in, analytics dashboards, timetable management, audit logging and Excel/CSV/PDF report exports.

## Team

| Member | Role |
|---|---|
| Deepak R | Developer |
| Yashaswini M | Developer |

## Project Overview

The system serves three roles:

- **Admin** — manages users (single or bulk import), classes, sections, subjects, teacher-subject assignments, the timetable, reports and the audit log.
- **Teacher** — views assigned subjects/classes, marks and edits attendance (with a full edit history), runs time-limited QR attendance sessions, reviews leave requests for relevant classes and exports reports.
- **Student** — views overall and subject-wise attendance, monthly trends and timetable, submits leave requests and tracks their status, checks in via QR and manages their profile/password.

## Features

### Phase 1 — Core
- Full MySQL 8 backend (InnoDB, utf8mb4) — no SQLite anywhere.
- Session authentication with hashed passwords (PBKDF2-SHA256 via Werkzeug).
- Role-based access control with reusable `@login_required` / `@role_required` decorators.
- Attendance marking per class/section/subject/date/period with statuses `present` / `absent` / `leave`.
- Duplicate prevention by a database-level unique constraint on `(student, subject, date, period)`.
- Leave workflow: student submits → relevant teacher approves/rejects → student sees the result.
- CSRF protection on every state-changing request; HttpOnly + SameSite session cookies.
- Login rate limiting (configurable attempts + lockout window).

### Phase 2 — Analytics, Timetable, Reports
- Admin / Teacher / Student dashboards with live counters.
- Daily, weekly and monthly attendance analytics with Chart.js trend charts.
- Low-attendance detection with a configurable threshold (default 75%) **and** a “classes needed to reach the threshold” calculation.
- Timetable management with backend conflict validation (double-booked teacher, clashing class slot).
- Report exports to **Excel** (openpyxl), **CSV** and **PDF** (ReportLab) with title, filters and summary.
- Server-side search, filtering, sorting and pagination on users, attendance history and audit logs.

### Phase 3 — QR, Notifications, Audit
- QR attendance sessions: the teacher generates a signed, expiring token; only its SHA-256 hash is stored server-side.
- Scans validate on the server: token signature, expiry, session active, student’s section match and duplicate check (DB constraint).
- In-app notifications with unread badge, mark-read and mark-all-read.
- Audit logging of logins, user changes, attendance edits, leave decisions and more — filterable by user/action/date/entity.
- Dedicated `attendance_edits` history (old status, new status, who, when, reason).

### Phase 4 — Operations
- 68-test pytest suite against a dedicated `attendance_test` database.
- Docker + Docker Compose with health checks and a wait-for-MySQL entrypoint.
- Structured logging to console and rotating file (`logs/attendance.log`).
- Custom error pages for 400/401/403/404/405/429/500 — no stack traces to end users.

## Technology Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.11+, Flask 3.x |
| Database | MySQL 8.x (mysql-connector-python) |
| Frontend | Jinja2, HTML5, CSS3, Bootstrap 5, vanilla JavaScript |
| Charts | Chart.js 4 |
| Exports | pandas + openpyxl (Excel), ReportLab (PDF) |
| QR | qrcode + Pillow |
| Config | python-dotenv |
| Tests | pytest |
| Deployment | Docker, Docker Compose, gunicorn |

## System Architecture

```text
Browser (Bootstrap 5 UI, Chart.js)
   ↓  HTTP
Flask app  (app.py — factory, error handlers, logging, security hooks)
   ↓
Routes layer  (routes/ — auth, admin, teacher, student, reports, notifications)
   ↓
Service layer (services/ — business rules, authorization, validation)
   ↓
Database layer (database/db.py — pooled, parameterized queries)
   ↓
MySQL 8  (InnoDB, utf8mb4, FKs + unique constraints)
```

## Database Architecture

`database/schemas/schema.sql` defines (all InnoDB / utf8mb4, with FKs, unique keys and indexes):

| Table | Purpose |
|---|---|
| `users` | Login accounts for all roles (hashed passwords) |
| `students` / `teachers` | Profile rows linked 1:1 to users |
| `classes` / `sections` | Academic structure (section belongs to a class) |
| `subjects` | Subjects with optional code |
| `teacher_subjects` | Which teacher teaches which subject (unique pair) |
| `timetable` | Class/section schedule with day, period, times + conflict-preventing unique key |
| `attendance` | One row per student+subject+date+period (`UNIQUE` — the dedupe guarantee) |
| `attendance_edits` | History of attendance status changes |
| `leave_requests` | Student leave workflow (pending/approved/rejected) |
| `attendance_sessions` | QR sessions (token **hash** only, expiry, active flag) |
| `notifications` | In-app user notifications |
| `audit_logs` | Who did what, when, from where |
| `settings` | Key/value application settings |

Relationships: `students.class_id → classes`, `students.section_id → sections`, `attendance.student_id → students`, `attendance.subject_id → subjects`, `leave_requests.student_id/teacher_id → students/teachers`, plus cascading deletes from `users`.

## User Roles

| Role | Can |
|---|---|
| Admin | Users CRUD + bulk import, classes/sections/subjects, teacher-subject assignments, timetable, all reports, audit logs |
| Teacher | Mark/edit attendance (own subjects only), QR sessions, attendance summaries, low-attendance alerts, leave decisions for relevant classes, own timetable, authorized reports |
| Student | Personal dashboards and attendance history, leave requests, QR check-in, timetable, profile + password change |

## Installation

### 1. Python setup

```bash
git clone <your-repository-url>
cd Attendance_System-Project
python -m venv .venv
# Windows:  .venv\Scripts\activate     Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
```

### 2. MySQL setup

Install MySQL 8 locally **or** use the bundled Docker service (step 6). The application needs a database user with create/read/write rights.

### 3. Environment configuration

```bash
cp .env.example .env    # then edit .env with your values
```

### 4. Database initialization

```bash
python reset_db.py           # creates schema if missing, prompts for admin password
python reset_db.py --reset   # drops and recreates everything (destructive!)
python seed_demo.py          # optional demo data for presentations
python check_users.py        # list accounts (diagnostics)
```

`reset_db.py` reads `ADMIN_PASSWORD` from the environment for unattended setups or prompts securely otherwise. The admin password is never stored in Git.

### 5. Run

```bash
python app.py
# open http://127.0.0.1:5000
```

Health check: `http://127.0.0.1:5000/health`

## MySQL Configuration

All connection values come from environment variables (see `.env.example`):

```env
FLASK_SECRET_KEY=replace-with-a-secure-secret
FLASK_DEBUG=0
FLASK_HOST=127.0.0.1
FLASK_PORT=5000

MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_DATABASE=attendance
MYSQL_USER=root
MYSQL_PASSWORD=
```

Never commit `.env`. `APP_ENV` selects `development` / `testing` / `production` configuration (default: development). Tests always use `TEST_MYSQL_DATABASE` (default `attendance_test`).

## Test Instructions

```bash
pip install -r requirements-dev.txt
pytest -q
```

The suite (68 tests) resets and uses the dedicated `attendance_test` database — it never touches your dev data. MySQL must be reachable (start the Docker service first, or point `TEST_MYSQL_DATABASE` settings at your own test server).

## Docker

```bash
# put real values in .env first (MYSQL_ROOT_PASSWORD, MYSQL_PASSWORD, FLASK_SECRET_KEY)
docker compose up --build -d
docker compose ps
docker compose logs -f web
docker compose down
```

The `web` container waits for the `mysql` health check, applies the schema idempotently, then serves with gunicorn on port 5000. Inside Docker, MySQL is reached by the service name `mysql`, not `localhost`.

## Project Structure

```text
Attendance_System-Project/
├── app.py                  # Flask factory, security hooks, error handlers
├── config.py               # env-driven dev/test/prod configuration
├── reset_db.py             # schema init / reset + admin creation
├── seed_demo.py            # optional demo data
├── check_users.py          # user listing diagnostic
├── entrypoint.sh           # Docker startup (wait for MySQL → schema → gunicorn)
├── Dockerfile
├── docker-compose.yml
├── .env.example
├── .gitignore
├── requirements.txt
├── requirements-dev.txt
├── database/
│   ├── db.py               # pooled MySQL access (parameterized queries)
│   ├── db_manager.py       # schema ensure/reset/wait-for-server
│   └── schemas/schema.sql  # canonical MySQL schema
├── routes/                 # auth, admin, teacher, student, reports, notifications, dashboard
├── services/               # attendance, leave, report, qr, timetable, academic, user, audit, notification
├── security/core.py        # login_required, role_required, CSRF, rate limiting
├── templates/              # base + admin/ teacher/ student/ reports/ errors/
├── static/css/
├── tests/                  # pytest suite (uses attendance_test DB)
├── docs/
└── uploads/
```

## Security Notes

- Passwords hashed with Werkzeug PBKDF2-SHA256 — never stored or logged in plaintext.
- Role authorization centralized in reusable decorators; every protected route is covered.
- CSRF token validated before views that rotate the session (e.g. login).
- All SQL is parameterized — no string-built queries.
- Session cookies: HttpOnly, SameSite=Lax, optional Secure behind HTTPS.
- Login rate limiting with a configurable lockout window.
- Uploads restricted by extension and a maximum size; processed files are deleted.
- Secrets only via environment variables; `.env` is gitignored.
- Error pages hide stack traces; DB error messages never expose credentials.
- QR tokens are HMAC-signed, expire quickly, and only their hash is stored.
- Duplicate attendance is impossible at the database level.
- Audit log records sensitive actions (logins, edits, decisions) with IP addresses.

## Future Enhancements

- AI-assisted attendance analytics (anomaly detection, dropout risk).
- Email/WhatsApp notification delivery.
- Mobile application with camera QR scanning.
- Biometric / face-recognition attendance.
- Cloud deployment with managed MySQL and HTTPS.
- Per-permission role system for larger institutions.

## Important Note

The repository contains **source code and configuration only**. Local databases, credentials, virtual environments, uploaded files, logs and generated artifacts stay out of Git — see `.gitignore`.
