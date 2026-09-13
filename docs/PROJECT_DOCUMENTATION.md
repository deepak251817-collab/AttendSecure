# Attendance Management System - Complete Documentation

## Table of Contents
1. [Project Overview](#project-overview)
2. [Technology Stack](#technology-stack)
3. [Database Design](#database-design)
4. [System Architecture](#system-architecture)
5. [Setup Instructions](#setup-instructions)
6. [Features and Functionality](#features-and-functionality)
7. [Application Routes](#application-routes)
8. [Database Schema Details](#database-schema-details)
9. [Security Implementation](#security-implementation)

## Project Overview

The Attendance Management System is a comprehensive web-based application designed for educational institutions to manage student attendance, leave requests, and teacher-subject assignments. The system provides different interfaces for administrators, teachers, and students, each with their specific functionalities.

### Key Features
- User authentication and role-based access control
- Student attendance tracking
- Leave request management
- Teacher-subject assignment
- Attendance reports generation
- User management

## Technology Stack

### Backend
- **Framework**: Flask 3.x (Python web framework)
- **WSGI Server**: Werkzeug 3.x
- **Data Processing**: 
  - Pandas 2.x
  - openpyxl 3.x
- **Security**: Werkzeug password hashing (PBKDF2-SHA256)

### Database
- **Primary Database**: SQLite (default)
- **Migration Target**: MySQL (via migrate_to_mysql.py)
- **Database Features**:
  - Foreign key constraints
  - Data integrity checks
  - Transaction support
  - Indexes for query performance

## Database Design

### Entity-Relationship Diagram
```
[users]
   ↑
   |
   +---------------+
   |              |
[teachers]    [students]
   |              |
   |              |
   v              v
[subjects]<---[attendance]
   ^
   |
[teacher_subjects]
        |
        v
[leave_requests]
```

### Detailed Table Structures

#### 1. Users Table
```sql
CREATE TABLE users (
    user_id INT PRIMARY KEY AUTO_INCREMENT,
    username VARCHAR(255) NOT NULL UNIQUE,
    password TEXT NOT NULL,
    role VARCHAR(50) NOT NULL CHECK (role IN ('admin', 'teacher', 'student')),
    class VARCHAR(50),
    section VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
```
- Primary authentication and user management table
- Supports three roles: admin, teacher, student
- Enforces unique usernames
- Stores hashed passwords for security

#### 2. Teachers Table
```sql
CREATE TABLE teachers (
    teacher_id INT PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(255) NOT NULL,
    user_id INT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
)
```
- Stores teacher-specific information
- Linked to users table for authentication
- Cascade deletion with user account

#### 3. Students Table
```sql
CREATE TABLE students (
    student_id INT PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(255) NOT NULL,
    student_id_number VARCHAR(50) NOT NULL UNIQUE,
    class VARCHAR(50) NOT NULL,
    section VARCHAR(50) NOT NULL,
    user_id INT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
)
```
- Manages student information
- Unique student ID number requirement
- Class and section tracking
- Linked to users table for authentication

#### 4. Subjects Table
```sql
CREATE TABLE subjects (
    subject_id INT PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(255) NOT NULL UNIQUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
```
- Maintains list of subjects
- Enforces unique subject names

#### 5. Teacher Subjects Table
```sql
CREATE TABLE teacher_subjects (
    id INT PRIMARY KEY AUTO_INCREMENT,
    teacher_id INT,
    subject_id INT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (teacher_id) REFERENCES teachers(teacher_id) ON DELETE CASCADE,
    FOREIGN KEY (subject_id) REFERENCES subjects(subject_id) ON DELETE CASCADE
)
```
- Junction table for teacher-subject assignments
- Enables many-to-many relationships
- Maintains teaching assignments history

#### 6. Attendance Table
```sql
CREATE TABLE attendance (
    id INT PRIMARY KEY AUTO_INCREMENT,
    student_id INT,
    subject_id INT,
    date DATE NOT NULL,
    status VARCHAR(50) CHECK(status IN ('Present', 'Absent', 'Leave', 'Approved Leave', 'Denied Leave')) NOT NULL,
    FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE,
    FOREIGN KEY (subject_id) REFERENCES subjects(subject_id) ON DELETE CASCADE
)
```
- Core table for attendance tracking
- Multiple status options for accurate tracking
- Date-wise attendance records
- Subject-wise attendance tracking

#### 7. Leave Requests Table
```sql
CREATE TABLE leave_requests (
    id INT PRIMARY KEY AUTO_INCREMENT,
    student_id INT,
    teacher_id INT,
    date DATE NOT NULL,
    reason TEXT,
    status VARCHAR(50) CHECK(status IN ('Pending', 'Approved', 'Denied')) NOT NULL DEFAULT 'Pending',
    FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE,
    FOREIGN KEY (teacher_id) REFERENCES teachers(teacher_id) ON DELETE CASCADE
)
```
- Manages student leave applications
- Tracks approval status
- Records leave reasons
- Links students with approving teachers

## System Architecture

### Component Structure
1. **Authentication Layer**
   - User login/logout management
   - Session handling
   - Role-based access control

2. **Business Logic Layer**
   - Attendance management
   - Leave request processing
   - User management
   - Report generation

3. **Data Access Layer**
   - Database interactions
   - Data validation
   - Transaction management

### Security Features
1. **Authentication**
   - Password hashing
   - Session management
   - Role-based access control

2. **Data Protection**
   - Input validation
   - SQL injection prevention
   - XSS protection

## Setup Instructions

### Prerequisites
1. Python 3.x
2. Virtual Environment

### Installation Steps
1. Clone the repository
2. Create virtual environment:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # Linux/Mac
   .venv\Scripts\activate     # Windows
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Initialize the SQLite database:
   ```bash
   python reset_db.py
   ```
5. Start the application:
   ```bash
   flask run
   ```
6. Open http://127.0.0.1:5000 in your browser
7. Run `python reset_db.py` and use the admin password supplied or generated during setup

**Note**: MySQL migration is optional. The app uses SQLite by default. To migrate to MySQL, run `python migrate_to_mysql.py` after installing `mysql-connector-python` and setting up a MySQL server.

## Features and Functionality

### Admin Features
- User management
- Subject management
- Teacher-subject assignment
- System configuration
- Report generation

### Teacher Features
- Mark attendance
- View class attendance
- Manage leave requests
- Generate reports
- View assigned subjects

### Student Features
- View attendance
- Submit leave requests
- View attendance reports
- Update profile

## Application Routes

### Authentication Routes
- `GET /` - Home page (redirects to login or dashboard)
- `GET/POST /login` - User login
- `GET /logout` - User logout
- `GET/POST /reset_password/<int:user_id>` - Admin resets a user's password

### Dashboard Routes
- `GET /dashboard` - Role-based dashboard (admin/teacher/student)
- `GET /admin_dashboard` - Admin overview dashboard

### User Management Routes
- `GET/POST /add_user` - Add a new user
- `GET/POST /edit_user/<int:user_id>` - Edit user details
- `GET /delete_user/<int:user_id>` - Delete a user
- `POST /upload_users` - Bulk import users from CSV/Excel

### Subject Management Routes
- `GET/POST /add_subject` - Add a new subject
- `GET/POST /assign_subject` - Assign subjects to teachers (via templates)

### Attendance Routes
- `GET/POST /mark_attendance` - Mark attendance (teacher)
- `POST /submit_attendance` - Submit attendance records
- `GET/POST /view_attendance` - View combined attendance records
- `GET /my_attendance` - Student's own attendance
- `GET/POST /edit_attendance/<int:id>` - Edit an attendance record
- `GET/POST /edit_attendance_by_info/<username>/<date>` - Edit attendance by username and date
- `GET /monthly_summary` - Monthly attendance summary
- `GET/POST /attendance_summary` - Overall attendance summary
- `GET/POST /low_attendance` - View students with low attendance
- `GET /export_attendance_report` - Export attendance to CSV/Excel

### Leave Management Routes
- `GET/POST /request_leave` - Student requests leave
- `GET/POST /view_leave_requests` - View leave requests (teacher/admin)
- `POST /handle_leave_request` - Approve/deny a leave request

## Database Migration

The system includes a migration script (`migrate_to_mysql.py`) that handles:
1. Data extraction from SQLite
2. Table creation in MySQL
3. Data transformation and cleaning
4. Foreign key relationship maintenance
5. Duplicate handling
6. Data integrity verification

### Migration Features
- Handles duplicate usernames
- Maintains referential integrity
- Preserves data relationships
- Validates data during transfer
- Error handling and logging

## Best Practices

### Code Organization
- Modular structure
- Clear separation of concerns
- Consistent naming conventions
- Comprehensive error handling

### Database
- Proper indexing
- Foreign key constraints
- Data validation
- Transaction management

### Security
- Password hashing
- Input sanitization
- Session management
- Access control

## Maintenance and Updates

### Regular Tasks
1. Database backup
2. Log rotation
3. Security updates
4. Performance monitoring

### Troubleshooting
1. Check application logs
2. Verify database connectivity
3. Monitor system resources
4. Review error reports

## Future Enhancements
1. Mobile application support
2. Biometric integration
3. Advanced reporting features
4. API expansion
5. Real-time notifications

This documentation provides a comprehensive overview of the Attendance Management System. For specific implementation details or technical questions, please refer to the source code or contact the development team. 