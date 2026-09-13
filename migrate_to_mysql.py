import sqlite3
try:
    import mysql.connector
    from mysql.connector import Error
except ImportError as exc:
    raise SystemExit("MySQL migration is optional. Install mysql-connector-python first.") from exc

def get_sqlite_data():
    try:
        sqlite_conn = sqlite3.connect('database/attendance.db')
        sqlite_cursor = sqlite_conn.cursor()
        
        # Get all tables
        sqlite_cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = sqlite_cursor.fetchall()
        
        data = {}
        for table in tables:
            table_name = table[0]
            # Get table structure
            sqlite_cursor.execute(f"PRAGMA table_info({table_name})")
            columns = sqlite_cursor.fetchall()
            # Get table data
            sqlite_cursor.execute(f"SELECT * FROM {table_name}")
            rows = sqlite_cursor.fetchall()
            data[table_name] = {
                'columns': columns,
                'rows': rows
            }
        return data
    finally:
        sqlite_conn.close()

def create_mysql_tables(mysql_cursor):
    # Drop existing database and create new one
    mysql_cursor.execute("DROP DATABASE IF EXISTS attendance")
    mysql_cursor.execute("CREATE DATABASE attendance")
    mysql_cursor.execute("USE attendance")
    
    # Temporarily disable foreign key checks
    mysql_cursor.execute("SET FOREIGN_KEY_CHECKS=0")
    
    # MySQL table creation statements
    create_users = """
    CREATE TABLE IF NOT EXISTS users (
        user_id INT PRIMARY KEY AUTO_INCREMENT,
        username VARCHAR(255) NOT NULL UNIQUE,
        password TEXT NOT NULL,
        role VARCHAR(50) NOT NULL CHECK (role IN ('admin', 'teacher', 'student')),
        class VARCHAR(50),
        section VARCHAR(50),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )"""

    create_teachers = """
    CREATE TABLE IF NOT EXISTS teachers (
        teacher_id INT PRIMARY KEY AUTO_INCREMENT,
        name VARCHAR(255) NOT NULL,
        user_id INT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
    )"""

    create_students = """
    CREATE TABLE IF NOT EXISTS students (
        student_id INT PRIMARY KEY AUTO_INCREMENT,
        name VARCHAR(255) NOT NULL,
        student_id_number VARCHAR(50) NOT NULL UNIQUE,
        class VARCHAR(50) NOT NULL,
        section VARCHAR(50) NOT NULL,
        user_id INT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
    )"""

    create_subjects = """
    CREATE TABLE IF NOT EXISTS subjects (
        subject_id INT PRIMARY KEY AUTO_INCREMENT,
        name VARCHAR(255) NOT NULL UNIQUE,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )"""

    create_teacher_subjects = """
    CREATE TABLE IF NOT EXISTS teacher_subjects (
        id INT PRIMARY KEY AUTO_INCREMENT,
        teacher_id INT,
        subject_id INT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (teacher_id) REFERENCES teachers(teacher_id) ON DELETE CASCADE,
        FOREIGN KEY (subject_id) REFERENCES subjects(subject_id) ON DELETE CASCADE
    )"""

    create_attendance = """
    CREATE TABLE IF NOT EXISTS attendance (
        id INT PRIMARY KEY AUTO_INCREMENT,
        student_id INT,
        subject_id INT,
        date DATE NOT NULL,
        status VARCHAR(50) CHECK(status IN ('Present', 'Absent', 'Leave', 'Approved Leave', 'Denied Leave')) NOT NULL,
        FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE,
        FOREIGN KEY (subject_id) REFERENCES subjects(subject_id) ON DELETE CASCADE
    )"""

    create_leave_requests = """
    CREATE TABLE IF NOT EXISTS leave_requests (
        id INT PRIMARY KEY AUTO_INCREMENT,
        student_id INT,
        teacher_id INT,
        date DATE NOT NULL,
        reason TEXT,
        status VARCHAR(50) CHECK(status IN ('Pending', 'Approved', 'Denied')) NOT NULL DEFAULT 'Pending',
        FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE,
        FOREIGN KEY (teacher_id) REFERENCES teachers(teacher_id) ON DELETE CASCADE
    )"""

    tables = [create_users, create_teachers, create_students, create_subjects, 
              create_teacher_subjects, create_attendance, create_leave_requests]
    
    for table in tables:
        mysql_cursor.execute(table)
    
    # Re-enable foreign key checks
    mysql_cursor.execute("SET FOREIGN_KEY_CHECKS=1")

def handle_duplicate_usernames(rows):
    seen_usernames = {}
    new_rows = []
    username_id_map = {}  # To track new user_ids
    next_id = 1
    
    for row in rows:
        old_id = row[0]
        username = row[1]
        if username in seen_usernames:
            seen_usernames[username] += 1
            new_username = f"{username}_{seen_usernames[username]}"
            new_row = list(row)
            new_row[0] = next_id  # Assign new ID
            new_row[1] = new_username
            new_rows.append(tuple(new_row))
            username_id_map[old_id] = next_id
        else:
            seen_usernames[username] = 0
            new_row = list(row)
            new_row[0] = next_id  # Assign new ID
            new_rows.append(tuple(new_row))
            username_id_map[old_id] = next_id
        next_id += 1
    
    return new_rows, username_id_map

def handle_duplicate_student_ids(rows):
    seen_ids = {}
    new_rows = []
    student_id_map = {}  # To track new student_ids
    next_id = 1
    
    for row in rows:
        old_id = row[0]
        student_id_number = row[2]  # student_id_number is at index 2
        if student_id_number in seen_ids:
            seen_ids[student_id_number] += 1
            new_student_id = f"{student_id_number}_{seen_ids[student_id_number]}"
            new_row = list(row)
            new_row[0] = next_id  # Assign new ID
            new_row[2] = new_student_id  # Update student_id_number
            new_rows.append(tuple(new_row))
            student_id_map[old_id] = next_id
        else:
            seen_ids[student_id_number] = 0
            new_row = list(row)
            new_row[0] = next_id  # Assign new ID
            new_rows.append(tuple(new_row))
            student_id_map[old_id] = next_id
        next_id += 1
    
    return new_rows, student_id_map

def update_foreign_keys(rows, id_map, id_index):
    new_rows = []
    for row in rows:
        new_row = list(row)
        old_id = row[id_index]
        if old_id in id_map:
            new_row[id_index] = id_map[old_id]
        new_rows.append(tuple(new_row))
    return new_rows

def migrate_data():
    try:
        # Get SQLite data
        sqlite_data = get_sqlite_data()
        
        # Connect to MySQL
        mysql_conn = mysql.connector.connect(
            host="localhost",
            user="root",
            password=input("Enter MySQL root password: ")
        )
        mysql_cursor = mysql_conn.cursor()
        
        # Create tables
        create_mysql_tables(mysql_cursor)
        
        # Process users first to get the ID mapping
        user_rows = sqlite_data['users']['rows']
        new_user_rows, user_id_map = handle_duplicate_usernames(user_rows)
        
        # Process students to get the ID mapping
        student_rows = sqlite_data['students']['rows']
        new_student_rows, student_id_map = handle_duplicate_student_ids(student_rows)
        
        # Insert data in the correct order to maintain referential integrity
        table_order = ['users', 'teachers', 'students', 'subjects', 
                      'teacher_subjects', 'attendance', 'leave_requests']
        
        # Temporarily disable foreign key checks during data insertion
        mysql_cursor.execute("SET FOREIGN_KEY_CHECKS=0")
        
        for table in table_order:
            if table in sqlite_data:
                data = sqlite_data[table]
                if data['rows']:
                    # Get column names
                    columns = [col[1] for col in data['columns']]
                    placeholders = ','.join(['%s'] * len(columns))
                    columns_str = ','.join(columns)
                    
                    # Handle data based on table
                    rows = data['rows']
                    if table == 'users':
                        rows = new_user_rows
                    elif table == 'teachers':
                        rows = update_foreign_keys(rows, user_id_map, 2)  # user_id is at index 2
                    elif table == 'students':
                        rows = new_student_rows
                    elif table == 'attendance':
                        rows = update_foreign_keys(rows, student_id_map, 1)  # student_id is at index 1
                    elif table == 'leave_requests':
                        rows = update_foreign_keys(rows, student_id_map, 1)  # student_id is at index 1
                    
                    try:
                        # Insert data
                        insert_query = f"INSERT INTO {table} ({columns_str}) VALUES ({placeholders})"
                        mysql_cursor.executemany(insert_query, rows)
                        print(f"Successfully inserted data into {table}")
                    except Error as e:
                        print(f"Error inserting into {table}: {e}")
                        raise
        
        # Re-enable foreign key checks
        mysql_cursor.execute("SET FOREIGN_KEY_CHECKS=1")
        
        mysql_conn.commit()
        print("\nMigration completed successfully!")
        
        # Verify the migration
        print("\nVerifying migration...")
        for table in table_order:
            mysql_cursor.execute(f"SELECT COUNT(*) FROM {table}")
            count = mysql_cursor.fetchone()[0]
            print(f"{table}: {count} records")
        
    except Error as e:
        print(f"Error: {e}")
        if 'mysql_conn' in locals():
            mysql_conn.rollback()
    finally:
        if 'mysql_conn' in locals() and mysql_conn.is_connected():
            mysql_cursor.close()
            mysql_conn.close()

if __name__ == "__main__":
    migrate_data() 