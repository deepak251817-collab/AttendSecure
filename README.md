# AttendSecure

### Secure Smart Attendance Management System

> **Smart, Secure & Simple Attendance Management**

AttendSecure is a full-stack attendance management platform designed for educational institutions. It provides role-based attendance management for **Administrators, Teachers, and Students**, with secure QR-based attendance, anti-proxy validation, attendance analytics, timetable management, leave workflows, notifications, audit logging, and reporting.

Built with **Flask and MySQL**, AttendSecure focuses on security, usability, maintainability, and practical deployment.

---

## ✨ Features

### 🔐 Authentication & Security

* Secure login and logout
* Password hashing
* Role-based access control
* Admin, Teacher, and Student roles
* Secure session management
* CSRF protection
* Parameterized MySQL queries
* Environment-based secrets
* Server-side input validation
* Login protection and rate limiting
* Audit logging
* Secure error handling

### 👨‍💼 Admin

* Manage students
* Manage teachers
* Manage classes and sections
* Manage subjects
* Assign subjects to teachers
* Manage timetable
* View attendance
* Generate attendance reports
* Monitor low-attendance students
* View audit logs
* Monitor suspicious attendance activity
* Manage notifications and settings

### 👨‍🏫 Teacher

* View assigned subjects
* View assigned classes
* Mark attendance
* Edit authorized attendance records
* Start secure QR attendance sessions
* View live attendance counts
* Manage relevant leave requests
* View student attendance
* View timetable
* Generate reports
* Monitor low-attendance students

### 👨‍🎓 Student

* View personal dashboard
* View overall attendance
* View subject-wise attendance
* View attendance history
* Scan QR codes for attendance
* Submit leave requests
* Track leave request status
* View timetable
* Receive notifications
* Download attendance reports
* Update profile
* Change password

---

## 🔒 Secure QR Attendance

AttendSecure uses multiple validation layers to **reduce proxy attendance**.

### Security layers

* Dynamic QR tokens
* Short-lived attendance sessions
* Authenticated students
* Server-side identity verification
* Class and section validation
* Subject validation
* Teacher authorization
* Duplicate attendance prevention
* Optional location verification
* Rate limiting
* Attendance attempt tracking
* Suspicious activity detection
* Audit logging

### Attendance flow

```text
Teacher Login
     ↓
Select Class / Subject / Period
     ↓
Start Attendance Session
     ↓
Dynamic QR Code
     ↓
Student Login
     ↓
Scan QR
     ↓
Server Validation
     ↓
Class / Subject Verification
     ↓
Duplicate Check
     ↓
Optional Location Verification
     ↓
Attendance Recorded
```

> QR attendance is designed to **reduce proxy attendance**. No normal web-based attendance system can guarantee that the person physically using a device is the legitimate account owner.

---

## 📊 Attendance Analytics

AttendSecure provides:

* Daily attendance
* Weekly attendance
* Monthly attendance
* Subject-wise attendance
* Class-wise attendance
* Student-wise attendance
* Attendance percentage
* Present / Absent / Leave distribution
* Attendance trends
* Low-attendance identification

### Attendance threshold

Default threshold:

```text
75%
```

Students below the threshold can be identified for follow-up.

---

## 📅 Timetable Management

Administrators can manage:

* Class
* Section
* Subject
* Teacher
* Day
* Period
* Start time
* End time

The system validates common timetable conflicts such as overlapping class or teacher assignments.

---

## 📝 Leave Management

Students can submit leave requests with:

* Start date
* End date
* Reason

Teachers can review and approve or reject relevant requests.

### Workflow

```text
Student
   ↓
Submit Leave Request
   ↓
Teacher Review
   ↓
Approve / Reject
   ↓
Student Notification
```

---

## 🔔 Notifications

The application provides in-app notifications for events such as:

* Leave approval
* Leave rejection
* Low-attendance warnings
* Attendance updates
* Important system activity

Users can view unread notifications and mark them as read.

---

## 🧾 Audit Logging

Important system actions are recorded for accountability.

Examples:

* Login/logout
* Attendance creation
* Attendance modification
* QR attendance attempts
* Failed verification
* Location verification failures
* Leave approval/rejection
* User creation
* Subject assignment
* Timetable changes

Passwords, secret keys, and database credentials must never be stored in audit logs.

---

## 📄 Reports

AttendSecure supports:

* Daily attendance reports
* Weekly attendance reports
* Monthly attendance reports
* Student attendance reports
* Subject reports
* Class reports
* Low-attendance reports

Depending on the enabled modules, reports can be exported to:

* Excel
* CSV
* PDF

---

## 🎨 UI & User Experience

AttendSecure provides a modern responsive interface with:

* AttendSecure branding
* Responsive sidebar
* Responsive navigation
* Dashboard cards
* Charts and analytics
* Search and filtering
* Toast notifications
* Loading states
* Empty states
* Error pages
* Profile menu
* Secure QR interface
* Smooth UI animations
* Responsive layouts

### 🌗 Theme Support

The application supports:

```text
Light
Dark
System
```

Theme preferences are persisted for the user.

Theme support covers:

* Header
* Sidebar
* Dashboard
* Cards
* Tables
* Forms
* Dropdowns
* Modals
* Charts
* Reports
* QR attendance pages
* Login page

---

## 🧰 Technology Stack

### Backend

* Python
* Flask
* Jinja2

### Database

* MySQL 8+

### Frontend

* HTML5
* CSS3
* JavaScript
* Bootstrap
* Chart.js where applicable

### Testing

* pytest
* Dedicated MySQL test database

### Deployment

* Docker
* Docker Compose

---

## 📁 Project Structure

```text
AttendSecure/
│
├── app.py
├── config.py
├── reset_db.py
├── seed_demo.py
├── check_users.py
│
├── requirements.txt
├── requirements-dev.txt
├── pytest.ini
├── Dockerfile
├── docker-compose.yml
├── entrypoint.sh
│
├── .env.example
├── .gitignore
├── README.md
│
├── database/
│   ├── db_manager.py
│   └── schemas/
│       └── schema.sql
│
├── routes/
├── services/
├── security/
│
├── templates/
├── static/
│   ├── css/
│   ├── js/
│   └── images/
│
├── tests/
├── docs/
│
└── uploads/
    └── .gitkeep
```

> The structure may evolve as the project is developed.

---

## ⚙️ Requirements

Install:

* Python 3.11+
* MySQL 8+
* Git

For Docker:

* Docker
* Docker Compose

---

## 🚀 Local Installation

### 1. Clone the repository

```bash
git clone https://github.com/YOUR_USERNAME/AttendSecure.git
cd AttendSecure
```

Replace `YOUR_USERNAME` with your GitHub username.

### 2. Create a virtual environment

#### Windows

```powershell
python -m venv .venv
.venv\Scripts\activate
```

#### Linux / macOS

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

For development and testing:

```bash
pip install -r requirements-dev.txt
```

---

## 🗄️ MySQL Configuration

Create the database:

```sql
CREATE DATABASE attendance
CHARACTER SET utf8mb4
COLLATE utf8mb4_unicode_ci;
```

Create a local `.env` file using `.env.example` as a template.

Example:

```env
FLASK_SECRET_KEY=replace-with-a-secure-random-secret

MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_DATABASE=attendance
MYSQL_USER=root
MYSQL_PASSWORD=your_mysql_password

FLASK_DEBUG=0
FLASK_HOST=127.0.0.1
FLASK_PORT=5000
```

### Important

Never commit `.env`.

Only commit:

```text
.env.example
```

Never publish your MySQL password or application secret.

---

## 🗃️ Database Initialization

Initialize the MySQL database:

```bash
python reset_db.py
```

The main schema is maintained in:

```text
database/schemas/schema.sql
```

For local demonstration data, where supported:

```bash
python seed_demo.py
```

Use demo credentials only for local development.

---

## ▶️ Run the Application

```bash
python app.py
```

Open:

```text
http://127.0.0.1:5000
```

---

## 🐳 Docker

Build and start:

```bash
docker compose up --build
```

Stop:

```bash
docker compose down
```

Remove containers and local development volumes:

```bash
docker compose down -v
```

> Use `docker compose down -v` carefully because it can remove local MySQL development data.

---

## 🧪 Testing

Use a dedicated MySQL test database.

Run:

```bash
pytest -q
```

The test suite covers areas such as:

* Authentication
* Authorization
* Attendance
* Duplicate prevention
* Leave management
* Reports
* QR attendance
* Security validation
* Notifications
* Audit logging

Do not run destructive tests against the real development database.

---

## 🔐 Environment Variables

Main configuration:

```text
FLASK_SECRET_KEY
MYSQL_HOST
MYSQL_PORT
MYSQL_DATABASE
MYSQL_USER
MYSQL_PASSWORD
FLASK_DEBUG
FLASK_HOST
FLASK_PORT
```

Additional feature configuration may include:

```text
QR refresh interval
Attendance session duration
Location verification
Attendance radius
Rate limiting
```

See `.env.example` for the supported configuration.

---

## 👥 Team

### Deepak R

* Full-stack development
* MySQL/database integration
* Authentication and security
* Attendance functionality
* QR attendance

### Yashaswini M

* Frontend/UI development
* User experience
* Testing
* Documentation
* Feature integration

> Team responsibilities may evolve during development.

---

## 📌 Project Goals

AttendSecure aims to:

* Simplify attendance management
* Reduce manual attendance work
* Improve attendance visibility
* Reduce proxy attendance
* Provide useful attendance analytics
* Simplify report generation
* Improve student-teacher communication
* Maintain an auditable attendance history
* Provide a secure and maintainable architecture

---

## 🔮 Future Enhancements

Potential future improvements include:

* Email notifications
* Mobile application
* Advanced attendance analytics
* AI-assisted attendance insights
* Cloud deployment
* Advanced anomaly detection
* Multi-campus institutional support

These are future possibilities and should not be considered implemented unless they exist in the current codebase.

---

## 🛡️ Security Guidelines

Never commit:

```text
.env
database passwords
API keys
secret keys
real student data
real user passwords
private certificates
database dumps
runtime logs
```

The repository should contain configuration templates rather than real credentials.

---

## 📜 License

This project is intended to be released under the **MIT License**.

See the [`LICENSE`](LICENSE) file for details.

---

## 🔗 Repository

**Project Name:** AttendSecure

**Repository:**

```text
https://github.com/deepak251817-collab/AttendSecure
```

**GitHub Description:**

> Smart and secure attendance management system with dynamic QR attendance, analytics, reports, notifications, and anti-proxy protection.

---

# AttendSecure

### Smart, Secure & Simple Attendance Management

**Built by Deepak R & Yashaswini M**
