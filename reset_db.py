import getpass
import os
import secrets
import sqlite3
from pathlib import Path

from werkzeug.security import generate_password_hash

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = Path(os.getenv("ATTENDANCE_DB_PATH", BASE_DIR / "database" / "attendance.db")).expanduser()
SCHEMA_PATH = BASE_DIR / "database" / "schemas" / "schema.sql"

def reset_database():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    if DB_PATH.exists():
        DB_PATH.unlink()
        print("Existing database removed.")
    conn = sqlite3.connect(str(DB_PATH))
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
        admin_password = os.getenv("ADMIN_PASSWORD") or getpass.getpass("Set admin password (leave blank to generate one): ")
        generated_password = False
        if not admin_password:
            admin_password = secrets.token_urlsafe(12)
            generated_password = True
        conn.execute("INSERT INTO users (username, password, role) VALUES (?, ?, 'admin')", ("admin", generate_password_hash(admin_password, method="pbkdf2:sha256")))
        conn.commit()
        print(f"Database initialized at: {DB_PATH}")
        print("Admin username: admin")
        if generated_password:
            print(f"Generated admin password (save it now): {admin_password}")
        else:
            print("Admin password set from your input / ADMIN_PASSWORD.")
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

if __name__ == "__main__":
    reset_database()
