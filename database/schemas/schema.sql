-- Combined Database Schema

-- Users table (core table, no dependencies)
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    username TEXT NOT NULL UNIQUE,
    password TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('admin', 'teacher', 'student')),
    class TEXT,
    section TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Teachers table (depends on users)
CREATE TABLE IF NOT EXISTS teachers (
    teacher_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    user_id INTEGER UNIQUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

-- Students table (depends on users)
CREATE TABLE IF NOT EXISTS students (
    student_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    student_id_number TEXT NOT NULL UNIQUE,
    class TEXT NOT NULL,
    section TEXT NOT NULL,
    user_id INTEGER UNIQUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

-- Subjects table (no dependencies)
CREATE TABLE IF NOT EXISTS subjects (
    subject_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Teacher Subjects table (depends on teachers and subjects)
CREATE TABLE IF NOT EXISTS teacher_subjects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    teacher_id INTEGER,
    subject_id INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (teacher_id) REFERENCES teachers(teacher_id) ON DELETE CASCADE,
    FOREIGN KEY (subject_id) REFERENCES subjects(subject_id) ON DELETE CASCADE,
    UNIQUE(teacher_id, subject_id)
);

-- Attendance table (depends on users and subjects)
CREATE TABLE IF NOT EXISTS attendance (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER,
    subject_id INTEGER,
    date TEXT NOT NULL,
    time TEXT,
    status TEXT CHECK(status IN ('Present', 'Absent', 'Leave', 'Approved Leave', 'Denied Leave')) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (student_id) REFERENCES users(user_id) ON DELETE CASCADE,
    FOREIGN KEY (subject_id) REFERENCES subjects(subject_id) ON DELETE CASCADE
);

-- Leave Requests table (depends on users and teachers)
CREATE TABLE IF NOT EXISTS leave_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER,
    teacher_id INTEGER,
    date TEXT NOT NULL,
    reason TEXT,
    status TEXT CHECK(status IN ('Pending', 'Approved', 'Denied')) NOT NULL DEFAULT 'Pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (student_id) REFERENCES users(user_id) ON DELETE CASCADE,
    FOREIGN KEY (teacher_id) REFERENCES teachers(teacher_id) ON DELETE CASCADE
);

-- Create indexes for better query performance
CREATE INDEX IF NOT EXISTS idx_attendance_student ON attendance(student_id);
CREATE INDEX IF NOT EXISTS idx_attendance_date ON attendance(date);
CREATE INDEX IF NOT EXISTS idx_attendance_time ON attendance(time);
CREATE INDEX IF NOT EXISTS idx_leave_requests_student ON leave_requests(student_id);
CREATE INDEX IF NOT EXISTS idx_leave_requests_status ON leave_requests(status);
CREATE INDEX IF NOT EXISTS idx_teacher_subjects_teacher ON teacher_subjects(teacher_id);
CREATE INDEX IF NOT EXISTS idx_users_role ON users(role);

-- Admin credentials are created by reset_db.py, never stored in the schema.
CREATE UNIQUE INDEX IF NOT EXISTS idx_attendance_unique
    ON attendance(student_id, subject_id, date);
