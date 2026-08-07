# Attendance Management System

A Flask-based attendance and leave-management web application for admins, teachers, and students.

## Features
- Admin dashboard for managing users, subjects, and teacher assignments
- Teacher tools for marking attendance, reviewing leave requests, and viewing summaries
- Student view for checking attendance, requesting leave, and seeing monthly progress
- CSV/Excel bulk user import
- Dark/light theme support
- SQLite-backed storage with schema initialization

## Tech Stack
- Python 3.11+
- Flask
- Jinja2
- SQLite
- pandas and openpyxl for bulk import/export

## Project Structure
- app.py: Main Flask application and routes
- database/: SQLite database file and schema
- templates/: HTML pages for the web UI
- uploads/: Temporary storage for imported files
- reset_db.py: Rebuilds the database from the schema

## Setup
1. Create and activate a virtual environment
   ```bash
   python -m venv .venv
   .venv\Scripts\activate
   ```
2. Install dependencies
   ```bash
   pip install -r requirements.txt
   ```
3. Initialize the database
   ```bash
   python reset_db.py
   ```
4. Start the app
   ```bash
   flask run
   ```
5. Open http://127.0.0.1:5000

## Default Login
- Username: admin
- Password: admin123

> Change the admin password after the first login.

## Notes
- The app uses SQLite by default.
- Bulk imports support CSV and Excel files.
- Local runtime artifacts such as `.venv`, `database/attendance.db`, `__pycache__`, and uploaded files are ignored by Git and can be regenerated or removed when no longer needed.

## Cleanup
- Keep source files, templates, and schema files under version control.
- Leave generated runtime files out of the repository.
