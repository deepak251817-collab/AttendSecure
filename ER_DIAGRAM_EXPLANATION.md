# Entity Relationship Diagram Explanation

## Core Entities

### 1. Users Table
- **Purpose**: Central authentication and user management
- **Key Fields**:
  - `id`: Unique identifier (Primary Key)
  - `username`: Login credential
  - `password_hash`: Encrypted password
  - `role`: User type (admin/teacher/student)
- **Relationships**: Parent table for Teachers and Students

### 2. Teachers Table
- **Purpose**: Stores teacher-specific information
- **Key Fields**:
  - `id`: Unique identifier
  - `user_id`: Links to Users table
  - `name`: Teacher's full name
  - `email`: Contact information
  - `phone`: Contact number
- **Relationships**:
  - One-to-One with Users
  - One-to-Many with TeacherSubjects

### 3. Students Table
- **Purpose**: Manages student information
- **Key Fields**:
  - `id`: Unique identifier
  - `user_id`: Links to Users table
  - `name`: Student's full name
  - `roll_number`: Unique student identifier
  - `class_info`: Class/Grade information
- **Relationships**:
  - One-to-One with Users
  - One-to-Many with Attendance and LeaveRequests

### 4. Subjects Table
- **Purpose**: Course/subject management
- **Key Fields**:
  - `id`: Unique identifier
  - `name`: Subject name
  - `code`: Subject code
  - `description`: Detailed information
- **Relationships**:
  - Many-to-Many with Teachers (through TeacherSubjects)
  - One-to-Many with Attendance

## Junction Tables

### 5. TeacherSubjects Table
- **Purpose**: Maps teachers to their subjects
- **Key Fields**:
  - `id`: Unique identifier
  - `teacher_id`: Links to Teachers
  - `subject_id`: Links to Subjects
- **Relationships**: Implements Many-to-Many between Teachers and Subjects

## Tracking Tables

### 6. Attendance Table
- **Purpose**: Daily attendance records
- **Key Fields**:
  - `id`: Unique identifier
  - `student_id`: Links to Students
  - `subject_id`: Links to Subjects
  - `date`: Attendance date
  - `status`: present/absent/late
  - `marked_by`: Teacher who marked attendance
- **Relationships**:
  - Many-to-One with Students
  - Many-to-One with Subjects

### 7. LeaveRequests Table
- **Purpose**: Managing student absences
- **Key Fields**:
  - `id`: Unique identifier
  - `student_id`: Links to Students
  - `start_date`: Leave start date
  - `end_date`: Leave end date
  - `status`: pending/approved/rejected
  - `approved_by`: Staff who processed request
- **Relationships**:
  - Many-to-One with Students
  - Many-to-One with Users (for approval)

## Key Relationships Explained

1. **User Management Flow**:
   ```
   Users (1) ──┬── (0..1) Teachers
               └── (0..1) Students
   ```
   Each user can be either a teacher or student (or admin)

2. **Subject Assignment Flow**:
   ```
   Teachers (1) ── (*) TeacherSubjects (*) ── (1) Subjects
   ```
   Teachers can teach multiple subjects, and subjects can have multiple teachers

3. **Attendance Tracking Flow**:
   ```
   Students (1) ── (*) Attendance (*) ── (1) Subjects
   ```
   Records which student attended which subject

4. **Leave Management Flow**:
   ```
   Students (1) ── (*) LeaveRequests ── (*) Users
   ```
   Students can submit multiple leave requests, approved by staff users

## Data Integrity Features

1. **Timestamps**:
   - `created_at`: Record creation time
   - `updated_at`: Last modification time
   - Present in all tables for audit trails

2. **Status Enums**:
   - Attendance: present/absent/late
   - Leave Requests: pending/approved/rejected
   - User Roles: admin/teacher/student

3. **Foreign Key Constraints**:
   - Ensures referential integrity
   - Prevents orphaned records
   - Maintains data consistency

## Design Benefits

1. **Scalability**:
   - Separate tables for different entities
   - Efficient relationship management
   - Easy to add new features

2. **Data Integrity**:
   - Strong relationships
   - Status tracking
   - Audit trails

3. **Flexibility**:
   - Multiple teachers per subject
   - Comprehensive attendance tracking
   - Detailed leave management

4. **Security**:
   - Role-based access
   - Password hashing
   - Activity tracking 