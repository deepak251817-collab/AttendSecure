# AttendSecure

### Secure Smart Attendance Management System

> **Smart, Secure & Simple Attendance Management**

AttendSecure is a Flask + MySQL attendance management platform for educational institutions with separate **Admin, Teacher, and Student** roles.

## ✨ Features

* 🔐 Secure authentication and role-based access
* 👨‍💼 Admin, Teacher and Student dashboards
* ✅ Attendance marking and history
* 📷 Dynamic QR-based attendance
* 🛡️ Anti-proxy attendance validation
* 📍 Optional location verification
* 📊 Attendance analytics and low-attendance tracking
* 📅 Timetable management
* 📝 Leave request and approval workflow
* 🔔 In-app notifications
* 🧾 Audit logging
* 📄 Excel, CSV and PDF reports
* 🌗 Light, Dark and System themes
* 📱 Responsive and animated UI
* 🐳 Docker support

## 🔒 Secure QR Attendance

```text
Teacher
   ↓
Start Attendance Session
   ↓
Dynamic QR
   ↓
Student Scans QR
   ↓
Server Validation
   ↓
Class / Subject Check
   ↓
Duplicate Check
   ↓
Optional Location Check
   ↓
Attendance Recorded
```

QR attendance is designed to **reduce proxy attendance** through multiple validation layers.

## 🧰 Tech Stack

**Backend:** Python, Flask, Jinja2
**Database:** MySQL 8+
**Frontend:** HTML, CSS, JavaScript, Bootstrap
**Testing:** pytest
**Deployment:** Docker, Docker Compose

## 📁 Project Structure

```text
AttendSecure/
├── app.py
├── config.py
├── reset_db.py
├── seed_demo.py
├── requirements.txt
├── requirements-dev.txt
├── Dockerfile
├── docker-compose.yml
├── .env.example
├── .gitignore
├── database/
├── routes/
├── services/
├── security/
├── templates/
├── static/
├── tests/
└── docs/
```

## 🚀 Setup

### 1. Clone

```bash
git clone https://github.com/YOUR_USERNAME/AttendSecure.git
cd AttendSecure
```

### 2. Create virtual environment

Windows:

```powershell
python -m venv .venv
.venv\Scripts\activate
```

Linux/macOS:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure MySQL

Create the database:

```sql
CREATE DATABASE attendance
CHARACTER SET utf8mb4
COLLATE utf8mb4_unicode_ci;
```

Create `.env` from `.env.example`:

```env
FLASK_SECRET_KEY=your-secret-key

MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_DATABASE=attendance
MYSQL_USER=root
MYSQL_PASSWORD=your_mysql_password

FLASK_DEBUG=0
FLASK_HOST=127.0.0.1
FLASK_PORT=5000
```

### 5. Initialize database

```bash
python reset_db.py
```

### 6. Run

```bash
python app.py
```

Open:

```text
http://127.0.0.1:5000
```

## 🧪 Testing

```bash
pytest -q
```

Use a dedicated test database and never run destructive tests against your development database.

## 🐳 Docker

```bash
docker compose up --build
```

Stop:

```bash
docker compose down
```

## 👥 Team

**Deepak R**
Full-stack development, database integration, security, attendance and QR functionality.

**Yashaswini M**
Frontend/UI, user experience, testing, documentation and feature integration.

## 🔐 Security

Never commit:

```text
.env
database passwords
API keys
secret keys
real student data
real passwords
database dumps
runtime logs
```

Use `.env.example` for configuration templates.

## 📜 License

This project is licensed under the **MIT License**.

See [`LICENSE`](LICENSE) for details.

---

### AttendSecure

**Smart, Secure & Simple Attendance Management**

Built by **Deepak R & Yashaswini M**
