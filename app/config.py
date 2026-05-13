from __future__ import annotations

import os


def env_bool(name: str, default: bool) -> bool:
    raw_value = os.environ.get(name)
    if raw_value is None:
        return default
    return raw_value.strip().lower() in {"1", "true", "yes", "on"}


def env_int(name: str, default: int) -> int:
    raw_value = os.environ.get(name)
    if raw_value is None:
        return default
    try:
        return int(raw_value.strip())
    except (TypeError, ValueError):
        return default


class Config:
    _secret_key = os.environ.get("SECRET_KEY", "").strip()
    SECRET_KEY = _secret_key if _secret_key and len(_secret_key) >= 32 else "dev-change-me-insecure-default"
    
    ADMIN_KEY = os.environ.get("ADMIN_KEY", "").strip()
    ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "").strip()
    ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "").strip()

    # SQLALCHEMY_DATABASE_URI is finalized in create_app() so we can safely use app.instance_path.
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL", "")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {}
    DATABASE_SSL_MODE = os.environ.get("DATABASE_SSL_MODE", "").strip().lower()
    DB_POOL_SIZE = env_int("DB_POOL_SIZE", 5)
    DB_MAX_OVERFLOW = env_int("DB_MAX_OVERFLOW", 10)
    DB_POOL_RECYCLE = env_int("DB_POOL_RECYCLE", 1800)
    DB_CONNECT_TIMEOUT = env_int("DB_CONNECT_TIMEOUT", 10)
    RATELIMIT_STORAGE_URI = os.environ.get("RATELIMIT_STORAGE_URI", "").strip()

    # Uploads (can be overridden in .env)
    UPLOAD_FOLDER = os.environ.get("UPLOAD_FOLDER", "")
    MAX_CONTENT_LENGTH = int(os.environ.get("MAX_UPLOAD_MB", "8")) * 1024 * 1024
    SUPABASE_URL = os.environ.get("SUPABASE_URL", "").strip()
    SUPABASE_SERVICE_ROLE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    SUPABASE_STORAGE_BUCKET = os.environ.get("SUPABASE_STORAGE_BUCKET", "stylebridge-uploads").strip()
    SUPABASE_USE_STORAGE = env_bool("SUPABASE_USE_STORAGE", False)

    # Flask settings
    FLASK_ENV = os.environ.get("FLASK_ENV", "production")
    DEBUG = FLASK_ENV == "development"
    TESTING = False
    LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")
    
    # Session & Cookie Security (enforced in production)
    SESSION_COOKIE_SECURE = env_bool("SESSION_COOKIE_SECURE", True)
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Strict'  # Stricter than Lax
    SESSION_COOKIE_NAME = "__Secure-Session" if SESSION_COOKIE_SECURE else "stylebridge-session"
    SESSION_REFRESH_EACH_REQUEST = True  # Refresh session timeout on each request
    PERMANENT_SESSION_LIFETIME = int(os.environ.get("PERMANENT_SESSION_LIFETIME", "3600"))  # 1 hour

    # Remember-me cookie security
    REMEMBER_COOKIE_SECURE = env_bool("REMEMBER_COOKIE_SECURE", True)
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_SAMESITE = 'Strict'  # Stricter than Lax
    REMEMBER_COOKIE_NAME = "__Secure-Remember" if REMEMBER_COOKIE_SECURE else "stylebridge-remember"
    REMEMBER_COOKIE_DURATION = int(os.environ.get("REMEMBER_COOKIE_DURATION", "2592000"))  # 30 days max

    # HTTPS enforcement
    PREFERRED_URL_SCHEME = os.environ.get("PREFERRED_URL_SCHEME", "https")
    FORCE_HTTPS = env_bool("FORCE_HTTPS", True)
    TRUST_PROXY_HEADERS = env_bool("TRUST_PROXY_HEADERS", bool(os.environ.get("RENDER")))
    TRUSTED_PROXY_COUNT = int(os.environ.get("TRUSTED_PROXY_COUNT", "1"))


class DevelopmentConfig(Config):
    FLASK_ENV = "development"
    DEBUG = True
    SQLALCHEMY_ECHO = env_bool("SQLALCHEMY_ECHO", True)  # Log SQL queries in dev
    # In development, allow non-HTTPS
    SESSION_COOKIE_SECURE = env_bool("SESSION_COOKIE_SECURE", False)
    SESSION_COOKIE_NAME = "__Secure-Session" if SESSION_COOKIE_SECURE else "stylebridge-session"
    REMEMBER_COOKIE_SECURE = env_bool("REMEMBER_COOKIE_SECURE", False)
    REMEMBER_COOKIE_NAME = "__Secure-Remember" if REMEMBER_COOKIE_SECURE else "stylebridge-remember"
    FORCE_HTTPS = env_bool("FORCE_HTTPS", False)


class ProductionConfig(Config):
    FLASK_ENV = "production"
    DEBUG = False
    TESTING = False
    SQLALCHEMY_ECHO = False
    
    # Enforce secure production settings
    SESSION_COOKIE_SECURE = True  # No override in production
    REMEMBER_COOKIE_SECURE = True  # No override in production
    FORCE_HTTPS = True  # No override in production
    PREFER_HTTPS = True


config = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "default": DevelopmentConfig,
}

