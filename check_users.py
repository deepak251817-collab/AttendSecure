import sqlite3
import os

def get_db():
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    db_dir = os.path.join(BASE_DIR, "database")
    if not os.path.exists(db_dir):
        os.makedirs(db_dir)
    db_path = os.path.join(db_dir, "attendance.db")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

def check_users():
    conn = get_db()
    users = conn.execute("SELECT username, role FROM users").fetchall()
    print("\nAvailable Users:")
    print("Username | Role")
    print("-" * 30)
    for user in users:
        print(f"{user['username']} | {user['role']}")
    conn.close()

if __name__ == "__main__":
    check_users() 