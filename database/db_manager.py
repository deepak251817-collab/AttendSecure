"""MySQL schema initialization and reset utilities.

Used by reset_db.py and the test suite. Talks to the server (no default
database selected) so it can create the schema database when needed.
"""
from __future__ import annotations

import logging
import time
from pathlib import Path

import mysql.connector
from mysql.connector import Error as MySQLError

logger = logging.getLogger("db")

SCHEMA_PATH = Path(__file__).resolve().parent / "schemas" / "schema.sql"


def ensure_database(cfg, database: str | None = None) -> None:
    """Create the target database if it does not exist yet."""
    database = database or cfg.MYSQL_DATABASE
    cnx = server_connect(cfg)
    try:
        cur = cnx.cursor()
        cur.execute(
            f"CREATE DATABASE IF NOT EXISTS `{database}` "
            "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
        )
        cur.close()
    finally:
        cnx.close()


def ensure_schema(cfg, database: str | None = None) -> None:
    """Apply database/schemas/schema.sql to the target database (idempotent)."""
    database = database or cfg.MYSQL_DATABASE
    ensure_database(cfg, database)
    sql = SCHEMA_PATH.read_text(encoding="utf-8")
    # Strip comment lines so semicolons inside comments cannot break splits.
    sql = "\n".join(
        line for line in sql.splitlines()
        if not line.strip().startswith("--")
    )
    cnx = server_connect(cfg, database)
    try:
        cur = cnx.cursor()
        for statement in filter(None, (s.strip() for s in sql.split(";"))):
            cur.execute(statement)
        cur.close()
        logger.info("Schema ensured on %s", database)
    finally:
        cnx.close()


def reset_database(cfg, database: str | None = None) -> None:
    """Drop and recreate every table in the database from the canonical schema.

    Works for database-scoped users (e.g. ``attendance_user`` in Docker) who
    cannot drop the database itself, by dropping tables with foreign key
    checks disabled instead.
    """
    database = database or cfg.MYSQL_DATABASE
    try:
        cnx = server_connect(cfg, database)
    except MySQLError as exc:
        if exc.errno == 1049:  # ER_BAD_DB_ERROR: unknown database
            ensure_database(cfg, database)
            cnx = server_connect(cfg, database)
        else:
            raise
    try:
        cur = cnx.cursor()
        try:
            cur.execute("SET FOREIGN_KEY_CHECKS = 0")
            cur.execute("SHOW TABLES")
            tables = [row[0] for row in cur.fetchall()]
            for table in tables:
                cur.execute(f"DROP TABLE IF EXISTS `{table}`")
            cur.execute("SET FOREIGN_KEY_CHECKS = 1")
        finally:
            cur.close()
    finally:
        cnx.close()
    ensure_schema(cfg, database)


def wait_for_server(cfg, timeout: int = 60, interval: float = 2.0) -> bool:
    """Block until MySQL accepts connections (used by Docker entrypoint)."""
    deadline = time.time() + timeout
    last_err = None
    while time.time() < deadline:
        try:
            cnx = server_connect(cfg)
            cnx.close()
            return True
        except MySQLError as exc:
            last_err = exc
            time.sleep(interval)
    logger.error("MySQL not reachable after %ss: %s", timeout, last_err)
    return False


def server_connect(cfg, database: str | None = None) -> mysql.connector.MySQLConnection:
    return mysql.connector.connect(
        host=cfg.MYSQL_HOST,
        port=cfg.MYSQL_PORT,
        user=cfg.MYSQL_USER,
        password=cfg.MYSQL_PASSWORD,
        database=database,
        connection_timeout=getattr(cfg, "MYSQL_CONNECTION_TIMEOUT", 10),
        autocommit=True,
        charset="utf8mb4",
    )
