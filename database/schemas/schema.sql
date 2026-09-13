-- =============================================================================
-- Attendance Management System - MySQL 8.x schema
-- Engine: InnoDB | Charset: utf8mb4 | Collation: utf8mb4_unicode_ci
-- Applied by database/db_manager.py (reset_db.py). Do not edit the live
-- database manually; change this file and re-run `python reset_db.py`.
-- =============================================================================

SET NAMES utf8mb4;

-- ----------------------------------------------------------------------------
-- Classes (e.g. "AIML", "CSE") and Sections (e.g. "A", "B")
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS classes (
    class_id   INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    name       VARCHAR(50) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uq_classes_name (name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS sections (
    section_id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    class_id   INT UNSIGNED NOT NULL,
    name       VARCHAR(20) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_sections_class FOREIGN KEY (class_id)
        REFERENCES classes (class_id) ON DELETE CASCADE,
    UNIQUE KEY uq_sections_class_name (class_id, name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------------------------------------------------------
-- Users (login accounts for all roles)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS users (
    user_id       INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    username      VARCHAR(50) NOT NULL,
    email         VARCHAR(120) NULL,
    password_hash VARCHAR(255) NOT NULL,
    full_name     VARCHAR(120) NULL,
    role          ENUM('admin', 'teacher', 'student') NOT NULL,
    is_active     TINYINT(1) NOT NULL DEFAULT 1,
    created_at    TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at    TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uq_users_username (username),
    KEY idx_users_role (role)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------------------------------------------------------
-- Students / Teachers (profile rows linked 1:1 to a user account)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS students (
    student_id      INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    user_id         INT UNSIGNED NOT NULL,
    register_number VARCHAR(40) NULL,
    class_id        INT UNSIGNED NULL,
    section_id      INT UNSIGNED NULL,
    created_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_students_user FOREIGN KEY (user_id)
        REFERENCES users (user_id) ON DELETE CASCADE,
    CONSTRAINT fk_students_class FOREIGN KEY (class_id)
        REFERENCES classes (class_id) ON DELETE SET NULL,
    CONSTRAINT fk_students_section FOREIGN KEY (section_id)
        REFERENCES sections (section_id) ON DELETE SET NULL,
    UNIQUE KEY uq_students_user (user_id),
    UNIQUE KEY uq_students_register_number (register_number),
    KEY idx_students_class_section (class_id, section_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS teachers (
    teacher_id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    user_id    INT UNSIGNED NOT NULL,
    department VARCHAR(80) NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_teachers_user FOREIGN KEY (user_id)
        REFERENCES users (user_id) ON DELETE CASCADE,
    UNIQUE KEY uq_teachers_user (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------------------------------------------------------
-- Subjects and teacher assignments
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS subjects (
    subject_id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    code       VARCHAR(20) NULL,
    name       VARCHAR(100) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uq_subjects_name (name),
    UNIQUE KEY uq_subjects_code (code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS teacher_subjects (
    id         INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    teacher_id INT UNSIGNED NOT NULL,
    subject_id INT UNSIGNED NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_ts_teacher FOREIGN KEY (teacher_id)
        REFERENCES teachers (teacher_id) ON DELETE CASCADE,
    CONSTRAINT fk_ts_subject FOREIGN KEY (subject_id)
        REFERENCES subjects (subject_id) ON DELETE CASCADE,
    UNIQUE KEY uq_teacher_subject (teacher_id, subject_id),
    KEY idx_ts_subject (subject_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------------------------------------------------------
-- Timetable (period scheduling per class/section)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS timetable (
    timetable_id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    class_id     INT UNSIGNED NOT NULL,
    section_id   INT UNSIGNED NOT NULL,
    subject_id   INT UNSIGNED NOT NULL,
    teacher_id   INT UNSIGNED NOT NULL,
    day_of_week  TINYINT UNSIGNED NOT NULL COMMENT '1=Monday .. 7=Sunday',
    period       TINYINT UNSIGNED NOT NULL,
    start_time   TIME NOT NULL,
    end_time     TIME NOT NULL,
    created_at   TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at   TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_tt_class FOREIGN KEY (class_id)
        REFERENCES classes (class_id) ON DELETE CASCADE,
    CONSTRAINT fk_tt_section FOREIGN KEY (section_id)
        REFERENCES sections (section_id) ON DELETE CASCADE,
    CONSTRAINT fk_tt_subject FOREIGN KEY (subject_id)
        REFERENCES subjects (subject_id) ON DELETE CASCADE,
    CONSTRAINT fk_tt_teacher FOREIGN KEY (teacher_id)
        REFERENCES teachers (teacher_id) ON DELETE CASCADE,
    CONSTRAINT chk_tt_days CHECK (day_of_week BETWEEN 1 AND 7),
    CONSTRAINT chk_tt_period CHECK (period BETWEEN 1 AND 12),
    CONSTRAINT chk_tt_times CHECK (end_time > start_time),
    UNIQUE KEY uq_tt_slot (class_id, section_id, day_of_week, period),
    KEY idx_tt_teacher_time (teacher_id, day_of_week, period),
    KEY idx_tt_subject (subject_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------------------------------------------------------
-- Attendance (one row per student+subject+date+period; DB-level dedupe)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS attendance (
    attendance_id   INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    student_id      INT UNSIGNED NOT NULL,
    subject_id      INT UNSIGNED NOT NULL,
    teacher_id      INT UNSIGNED NULL,
    class_id        INT UNSIGNED NULL,
    attendance_date DATE NOT NULL,
    period          TINYINT UNSIGNED NOT NULL DEFAULT 1,
    status          ENUM('present', 'absent', 'leave') NOT NULL,
    marked_by       INT UNSIGNED NULL COMMENT 'user_id who marked/last edited',
    marked_at       TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_att_student FOREIGN KEY (student_id)
        REFERENCES students (student_id) ON DELETE CASCADE,
    CONSTRAINT fk_att_subject FOREIGN KEY (subject_id)
        REFERENCES subjects (subject_id) ON DELETE CASCADE,
    CONSTRAINT fk_att_teacher FOREIGN KEY (teacher_id)
        REFERENCES teachers (teacher_id) ON DELETE SET NULL,
    CONSTRAINT fk_att_class FOREIGN KEY (class_id)
        REFERENCES classes (class_id) ON DELETE SET NULL,
    CONSTRAINT fk_att_marker FOREIGN KEY (marked_by)
        REFERENCES users (user_id) ON DELETE SET NULL,
    CONSTRAINT chk_att_status CHECK (status IN ('present', 'absent', 'leave')),
    UNIQUE KEY uq_attendance_record (student_id, subject_id, attendance_date, period),
    KEY idx_att_date (attendance_date),
    KEY idx_att_class_date (class_id, attendance_date),
    KEY idx_att_teacher (teacher_id),
    KEY idx_att_subject_date (subject_id, attendance_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- History of attendance status changes (Phase 3: edit audit trail)
CREATE TABLE IF NOT EXISTS attendance_edits (
    edit_id       INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    attendance_id INT UNSIGNED NOT NULL,
    old_status    ENUM('present', 'absent', 'leave') NOT NULL,
    new_status    ENUM('present', 'absent', 'leave') NOT NULL,
    changed_by    INT UNSIGNED NULL,
    reason        VARCHAR(255) NULL,
    created_at    TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_edit_attendance FOREIGN KEY (attendance_id)
        REFERENCES attendance (attendance_id) ON DELETE CASCADE,
    CONSTRAINT fk_edit_user FOREIGN KEY (changed_by)
        REFERENCES users (user_id) ON DELETE SET NULL,
    KEY idx_edit_attendance (attendance_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------------------------------------------------------
-- Leave requests (student -> teacher review workflow)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS leave_requests (
    leave_id    INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    student_id  INT UNSIGNED NOT NULL,
    teacher_id  INT UNSIGNED NULL COMMENT 'teacher reviewing the request',
    subject_id  INT UNSIGNED NULL,
    start_date  DATE NOT NULL,
    end_date    DATE NOT NULL,
    reason      TEXT NOT NULL,
    status      ENUM('pending', 'approved', 'rejected') NOT NULL DEFAULT 'pending',
    approved_by INT UNSIGNED NULL COMMENT 'teachers.teacher_id who decided',
    created_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_leave_student FOREIGN KEY (student_id)
        REFERENCES students (student_id) ON DELETE CASCADE,
    CONSTRAINT fk_leave_teacher FOREIGN KEY (teacher_id)
        REFERENCES teachers (teacher_id) ON DELETE SET NULL,
    CONSTRAINT fk_leave_subject FOREIGN KEY (subject_id)
        REFERENCES subjects (subject_id) ON DELETE SET NULL,
    CONSTRAINT fk_leave_approver FOREIGN KEY (approved_by)
        REFERENCES teachers (teacher_id) ON DELETE SET NULL,
    CONSTRAINT chk_leave_dates CHECK (end_date >= start_date),
    KEY idx_leave_status (status),
    KEY idx_leave_teacher_status (teacher_id, status),
    KEY idx_leave_student (student_id),
    KEY idx_leave_dates (start_date, end_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------------------------------------------------------
-- QR attendance sessions (only the token HASH is stored, never the token)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS attendance_sessions (
    session_id   INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    token_hash   CHAR(64) NOT NULL COMMENT 'sha256 hex of the signed token',
    teacher_id   INT UNSIGNED NOT NULL,
    subject_id   INT UNSIGNED NOT NULL,
    class_id     INT UNSIGNED NOT NULL,
    section_id   INT UNSIGNED NOT NULL,
    attendance_date DATE NOT NULL,
    period       TINYINT UNSIGNED NOT NULL DEFAULT 1,
    expires_at   DATETIME NOT NULL,
    is_active    TINYINT(1) NOT NULL DEFAULT 1,
    created_at   TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_sess_teacher FOREIGN KEY (teacher_id)
        REFERENCES teachers (teacher_id) ON DELETE CASCADE,
    CONSTRAINT fk_sess_subject FOREIGN KEY (subject_id)
        REFERENCES subjects (subject_id) ON DELETE CASCADE,
    CONSTRAINT fk_sess_class FOREIGN KEY (class_id)
        REFERENCES classes (class_id) ON DELETE CASCADE,
    CONSTRAINT fk_sess_section FOREIGN KEY (section_id)
        REFERENCES sections (section_id) ON DELETE CASCADE,
    UNIQUE KEY uq_session_token (token_hash),
    KEY idx_sess_expiry (expires_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------------------------------------------------------
-- In-app notifications
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS notifications (
    notification_id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    user_id         INT UNSIGNED NOT NULL,
    title           VARCHAR(150) NOT NULL,
    message         TEXT NULL,
    type            ENUM('info', 'leave', 'attendance', 'warning', 'session') NOT NULL DEFAULT 'info',
    is_read         TINYINT(1) NOT NULL DEFAULT 0,
    created_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_notif_user FOREIGN KEY (user_id)
        REFERENCES users (user_id) ON DELETE CASCADE,
    KEY idx_notif_user_unread (user_id, is_read),
    KEY idx_notif_created (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------------------------------------------------------
-- Audit log (who did what, when, from where)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS audit_logs (
    audit_id    INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    user_id     INT UNSIGNED NULL,
    action      VARCHAR(64) NOT NULL,
    entity_type VARCHAR(50) NULL,
    entity_id   INT UNSIGNED NULL,
    description TEXT NULL,
    ip_address  VARCHAR(45) NULL,
    created_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_audit_user FOREIGN KEY (user_id)
        REFERENCES users (user_id) ON DELETE SET NULL,
    KEY idx_audit_user (user_id),
    KEY idx_audit_action (action),
    KEY idx_audit_created (created_at),
    KEY idx_audit_entity (entity_type, entity_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------------------------------------------------------
-- Application settings (key/value; e.g. low attendance threshold)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS settings (
    setting_key   VARCHAR(64) PRIMARY KEY,
    setting_value VARCHAR(255) NOT NULL,
    updated_at    TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
