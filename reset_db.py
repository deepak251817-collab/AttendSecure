"""Initialize or reset the MySQL database for the Attendance System.

Usage:
    python reset_db.py            # create schema if missing, keep data
    python reset_db.py --reset    # DROP and recreate the database from schema

Admin account:
    * If ADMIN_PASSWORD env var is set, the admin password is taken from it.
    * Otherwise you are prompted (getpass) to set one.
    * A generated/typed password is printed once; it is never stored in Git.

Requires the values in .env (MYSQL_HOST, MYSQL_PORT, MYSQL_DATABASE,
MYSQL_USER, MYSQL_PASSWORD) to point at your MySQL server.
"""
from __future__ import annotations

import getpass
import sys

from config import get_config
from database.db_manager import ensure_schema, reset_database, wait_for_server
from services.user_service import hash_password


def _prompt_admin_password() -> str:
    import os

    pwd = os.getenv("ADMIN_PASSWORD")
    if pwd:
        print("Using ADMIN_PASSWORD from the environment.")
        return pwd
    while True:
        pwd = getpass.getpass("Set admin password (min 6 chars, blank = skip): ")
        if not pwd:
            print("Skipping admin creation — create one later from the app.")
            return ""
        if len(pwd) >= 6:
            return pwd
        print("Too short, try again.")


def main() -> int:
    do_reset = "--reset" in sys.argv
    cfg = get_config()()
    cfg.validate()

    print(f"Target MySQL: {cfg.MYSQL_USER}@{cfg.MYSQL_HOST}:{cfg.MYSQL_PORT}"
          f"/{cfg.MYSQL_DATABASE}")
    if not wait_for_server(cfg, timeout=30):
        print("ERROR: MySQL is not reachable. Is the server running?")
        print("Hint (Docker): docker compose up -d mysql")
        return 1

    if do_reset:
        print("Resetting database (all data will be lost)...")
        reset_database(cfg)
    else:
        print("Ensuring schema exists...")
        ensure_schema(cfg)

    # Create the default admin account if there are no admins yet.
    from database.db import get_db

    db = get_db(cfg)
    try:
        has_admin = db.query_value(
            "SELECT COUNT(*) FROM users WHERE role = 'admin'")
        if not has_admin:
            username = "admin"
            password = _prompt_admin_password()
            if password:
                db.execute(
                    "INSERT INTO users (username, password_hash, role) "
                    "VALUES (%s, %s, 'admin')",
                    (username, hash_password(password)),
                )
                db.commit()
                print(f"Admin account '{username}' created.")
        else:
            print("Admin account already exists; left untouched.")
    finally:
        db.close()

    print("Done. Start the app with:  python app.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
