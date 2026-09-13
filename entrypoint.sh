#!/bin/sh
set -e

echo "Waiting for MySQL to be reachable..."
python - <<'EOF'
import os
import time

import mysql.connector

host = os.getenv("MYSQL_HOST", "mysql")
port = int(os.getenv("MYSQL_PORT", "3306"))
user = os.getenv("MYSQL_USER", "attendance_user")
password = os.getenv("MYSQL_PASSWORD", "")

deadline = time.time() + 60
while True:
    try:
        mysql.connector.connect(host=host, port=port, user=user,
                                password=password,
                                connection_timeout=5, autocommit=True)
        print("MySQL is up.")
        break
    except mysql.connector.Error:
        if time.time() > deadline:
            raise SystemExit("MySQL not reachable after 60s")
        time.sleep(2)
EOF

echo "Applying database schema (idempotent)..."
python - <<'EOF'
from config import get_config
from database.db_manager import ensure_schema

ensure_schema(get_config()())
print("Schema ensured.")
EOF

echo "Starting gunicorn..."
exec gunicorn --bind "0.0.0.0:${FLASK_PORT:-5000}" \
    --workers 3 --threads 2 --timeout 120 "app:app"
