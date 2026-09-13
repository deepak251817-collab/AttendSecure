"""List user accounts in the MySQL database (diagnostic helper).

Usage: python check_users.py
"""
from __future__ import annotations

import sys

from config import get_config
from database.db import get_db


def main() -> int:
    cfg = get_config()()
    cfg.validate()
    db = get_db(cfg)
    try:
        rows = db.query(
            """
            SELECT u.username, u.role, u.is_active, u.full_name,
                   c.name AS class_name, sec.name AS section_name
            FROM users u
            LEFT JOIN students s ON s.user_id = u.user_id
            LEFT JOIN classes c ON c.class_id = s.class_id
            LEFT JOIN sections sec ON sec.section_id = s.section_id
            ORDER BY FIELD(u.role, 'admin', 'teacher', 'student'), u.username
            """
        )
        print(f"{'Username':<20} {'Role':<10} {'Active':<7} {'Class':<12} {'Section':<10}")
        print("-" * 65)
        for r in rows:
            print(f"{r['username']:<20} {r['role']:<10} "
                  f"{'yes' if r['is_active'] else 'NO':<7} "
                  f"{r['class_name'] or '-':<12} {r['section_name'] or '-':<10}")
        print(f"\nTotal: {len(rows)} users")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
