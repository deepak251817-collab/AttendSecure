"""Environment-driven configuration for the Attendance Management System.

All secrets and deployment-specific values are read from environment
variables (optionally via a local `.env` file) and are never hard-coded.
"""
import os
import secrets
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent

# Load a local .env file when present (gitignored; see .env.example).
load_dotenv(BASE_DIR / ".env")


def _env_bool(name: str, default: str = "0") -> bool:
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


class BaseConfig:
    """Shared configuration; subclassed per environment."""

    # Flask core
    SECRET_KEY = os.getenv("FLASK_SECRET_KEY")
    DEBUG = False
    TESTING = False

    # Password hashing (scrypt is the werkzeug default since 3.0; this
    # projects uses pbkdf2 for wider platform compatibility. Tests may
    # override with a cheaper method for speed.)
    PASSWORD_HASH_METHOD = os.getenv("PASSWORD_HASH_METHOD", "pbkdf2:sha256:600000")

    # Session security
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = _env_bool("SESSION_COOKIE_SECURE")  # enable behind HTTPS
    PERMANENT_SESSION_LIFETIME = 60 * 60 * 8  # 8 hours

    # MySQL connection
    MYSQL_HOST = os.getenv("MYSQL_HOST", "127.0.0.1")
    MYSQL_PORT = _env_int("MYSQL_PORT", 3306)
    MYSQL_DATABASE = os.getenv("MYSQL_DATABASE", "attendance")
    MYSQL_USER = os.getenv("MYSQL_USER", "attendance_user")
    MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "")
    MYSQL_CONNECTION_TIMEOUT = _env_int("MYSQL_CONNECTION_TIMEOUT", 10)
    MYSQL_POOL_NAME = "attendance_pool"

    # Uploads
    UPLOAD_FOLDER = str(BASE_DIR / "uploads")
    ALLOWED_EXTENSIONS = {"csv", "xlsx", "xls"}
    MAX_CONTENT_LENGTH = _env_int("MAX_UPLOAD_MB", 5) * 1024 * 1024

    # Security
    MAX_LOGIN_ATTEMPTS = _env_int("MAX_LOGIN_ATTEMPTS", 5)
    LOGIN_LOCKOUT_MINUTES = _env_int("LOGIN_LOCKOUT_MINUTES", 15)

    # Attendance / leaves
    LOW_ATTENDANCE_THRESHOLD = float(os.getenv("LOW_ATTENDANCE_THRESHOLD", "75"))
    QR_SESSION_MINUTES = _env_int("QR_SESSION_MINUTES", 5)

    @staticmethod
    def validate():
        """Fail fast on missing required secrets (called for non-test environments)."""
        if not BaseConfig.SECRET_KEY:
            raise RuntimeError(
                "FLASK_SECRET_KEY is not set. Copy .env.example to .env and set a "
                "long random value (e.g. output of: python -c \"import secrets; "
                "print(secrets.token_hex(32))\")."
            )


class DevelopmentConfig(BaseConfig):
    DEBUG = _env_bool("FLASK_DEBUG")


class TestingConfig(BaseConfig):
    TESTING = True
    SECRET_KEY = os.getenv("FLASK_SECRET_KEY", "test-only-secret-key")
    # Fast, test-only password hashing (NOT used outside tests).
    PASSWORD_HASH_METHOD = "pbkdf2:sha256:1000"
    # Tests always use the dedicated test database; falls back to a name
    # derived from the configured database so real data is never touched.
    MYSQL_DATABASE = os.getenv(
        "TEST_MYSQL_DATABASE", f"{BaseConfig.MYSQL_DATABASE}_test"
    )
    MYSQL_POOL_NAME = "attendance_test_pool"


class ProductionConfig(BaseConfig):
    # Secure-by-default in production; may be disabled explicitly (e.g. a
    # local Docker demo without TLS) via SESSION_COOKIE_SECURE=0.
    SESSION_COOKIE_SECURE = _env_bool("SESSION_COOKIE_SECURE", "1")

    @classmethod
    def validate(cls):
        BaseConfig.validate()
        if cls.DEBUG:
            raise RuntimeError("DEBUG must be disabled in production (FLASK_DEBUG=0).")


def get_config(name: str | None = None):
    """Return the config class selected via APP_ENV (default: development)."""
    name = (name or os.getenv("APP_ENV", "development")).lower()
    configs = {
        "development": DevelopmentConfig,
        "testing": TestingConfig,
        "production": ProductionConfig,
    }
    return configs.get(name, DevelopmentConfig)
