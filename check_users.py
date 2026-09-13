import os
import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = Path(os.getenv("ATTENDANCE_DB_PATH", BASE_DIR / "database" / "attendance.db")).expanduser()

if __name__ == "__main__":
    if not DB_PATH.exists():
        raise SystemExit("Database not found. Run: python reset_db.py")
    conn = sqlite3.connect(str(DB_PATH))
    rows = conn.execute("SELECT username, role FROM users ORDER BY role, username").fetchall()
    print("Username | Role")
    print("-" * 30)
    for username, role in rows:
        print(f"{username} | {role}")
    conn.close()
