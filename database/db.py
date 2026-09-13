"""Thin MySQL data-access layer used by routes, services and scripts.

Provides a small `Database` wrapper with dict rows, parameterized queries
and transaction helpers on top of mysql-connector-python pooling.
"""
from __future__ import annotations

import logging
from typing import Any, Iterable

import mysql.connector
from mysql.connector import Error as MySQLError
from mysql.connector import pooling

logger = logging.getLogger("db")

_pool: pooling.MySQLConnectionPool | None = None
_pool_key: tuple | None = None


class DatabaseError(MySQLError):
    """Raised for database failures; safe message only (no credentials)."""


def _get_pool(cfg) -> pooling.MySQLConnectionPool:
    global _pool, _pool_key
    key = (
        cfg.MYSQL_HOST,
        cfg.MYSQL_PORT,
        cfg.MYSQL_DATABASE,
        cfg.MYSQL_USER,
        getattr(cfg, "MYSQL_POOL_NAME", "attendance_pool"),
    )
    if _pool is None or _pool_key != key:
        try:
            _pool = pooling.MySQLConnectionPool(
                pool_name=key[4],
                pool_size=10,
                pool_reset_session=True,
                host=key[0],
                port=key[1],
                database=key[2],
                user=key[3],
                password=cfg.MYSQL_PASSWORD,
                connection_timeout=getattr(cfg, "MYSQL_CONNECTION_TIMEOUT", 10),
                autocommit=False,
                charset="utf8mb4",
                collation="utf8mb4_unicode_ci",
            )
            _pool_key = key
        except MySQLError as exc:
            logger.error("Could not create MySQL pool: %s", exc.errno)
            raise DatabaseError(
                "Database connection failed. Check that MySQL is running and "
                "MYSQL_HOST/MYSQL_PORT/MYSQL_USER/MYSQL_PASSWORD are correct."
            ) from exc
    return _pool


class Database:
    """Connection wrapper. Use as a context manager to get commit/rollback."""

    def __init__(self, cfg):
        self._cfg = cfg
        try:
            self._cnx = _get_pool(cfg).get_connection()
            self._cursor = self._cnx.cursor(dictionary=True)
        except MySQLError as exc:
            logger.error("MySQL connection failed (errno=%s)", getattr(exc, "errno", "?"))
            raise DatabaseError(
                "Could not connect to the database. Please try again later."
            ) from exc

    # -- reads ---------------------------------------------------------------
    def query(self, sql: str, params: Iterable[Any] = ()) -> list[dict]:
        self._cursor.execute(sql, tuple(params))
        return self._cursor.fetchall()

    def query_one(self, sql: str, params: Iterable[Any] = ()) -> dict | None:
        self._cursor.execute(sql, tuple(params))
        return self._cursor.fetchone()

    def query_value(self, sql: str, params: Iterable[Any] = ()) -> Any:
        row = self.query_one(sql, params)
        if not row:
            return None
        return next(iter(row.values()))

    # -- writes (commit explicitly or use the context manager) ---------------
    def execute(self, sql: str, params: Iterable[Any] = ()) -> int:
        """Run a write statement and return lastrowid (no commit)."""
        self._cursor.execute(sql, tuple(params))
        return self._cursor.lastrowid

    def executemany(self, sql: str, seq: list[tuple]) -> None:
        self._cursor.executemany(sql, seq)

    def commit(self) -> None:
        self._cnx.commit()

    def rollback(self) -> None:
        self._cnx.rollback()

    # -- lifecycle ------------------------------------------------------------
    def close(self) -> None:
        try:
            self._cursor.close()
        except Exception:
            pass
        try:
            # Pooled connections return to the pool on close.
            self._cnx.close()
        except Exception:
            pass

    def __enter__(self) -> "Database":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        try:
            if exc_type is None:
                self.commit()
            else:
                self.rollback()
        finally:
            self.close()

    # -- introspection --------------------------------------------------------
    def ping(self) -> bool:
        try:
            self.query("SELECT 1")
            return True
        except MySQLError:
            return False


def get_db(cfg=None) -> Database:
    if cfg is None:
        from config import get_config

        cfg = get_config()()
    return Database(cfg)


def server_connection(cfg) -> mysql.connector.MySQLConnection:
    """Connect WITHOUT selecting a database (used to create the schema)."""
    return mysql.connector.connect(
        host=cfg.MYSQL_HOST,
        port=cfg.MYSQL_PORT,
        user=cfg.MYSQL_USER,
        password=cfg.MYSQL_PASSWORD,
        connection_timeout=getattr(cfg, "MYSQL_CONNECTION_TIMEOUT", 10),
        autocommit=True,
        charset="utf8mb4",
    )


def close_db(exc) -> None:
    """Flask teardown helper; no-op if nothing stored."""
