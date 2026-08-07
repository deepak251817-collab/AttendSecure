import os
import sqlite3
from werkzeug.security import generate_password_hash

def reset_database():
    # Database path
    db_path = os.path.join('database', 'attendance.db')
    schema_path = os.path.join('database', 'schemas', 'schema.sql')

    # Delete existing database if it exists
    if os.path.exists(db_path):
        os.remove(db_path)
        print("Existing database deleted.")

    # Ensure database directory exists
    os.makedirs(os.path.dirname(db_path), exist_ok=True)

    # Create new database
    conn = sqlite3.connect(db_path)
    
    try:
        # Read schema
        with open(schema_path, 'r') as f:
            schema = f.read()
        
        # Execute schema (this creates tables)
        conn.executescript(schema)
        
        # Create admin user with properly hashed password
        admin_password = "admin123"
        hashed_password = generate_password_hash(admin_password)
        
        # Delete any existing admin user first
        conn.execute("DELETE FROM users WHERE username = 'admin'")
        
        # Insert new admin user
        conn.execute("""
            INSERT INTO users (username, password, role)
            VALUES (?, ?, 'admin')
        """, ('admin', hashed_password))
        
        conn.commit()
        
        print("""Database reset successfully!
        
Default admin credentials:
Username: admin
Password: admin123

Please change the password after first login.""")
        
    except Exception as e:
        print(f"Error resetting database: {str(e)}")
        if os.path.exists(db_path):
            os.remove(db_path)
    finally:
        conn.close()

if __name__ == "__main__":
    reset_database() 