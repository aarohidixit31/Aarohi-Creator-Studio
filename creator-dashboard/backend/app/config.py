import os
from urllib.parse import urlparse

from .database import DATABASE_URL
from .services.email import email_is_configured
from .services.storage import cloudinary_is_configured


def is_production() -> bool:
    return os.getenv("ENVIRONMENT", "development").casefold() == "production"


def cors_origins() -> list[str]:
    configured = [
        value.strip().rstrip("/")
        for value in os.getenv("CORS_ORIGINS", "").split(",")
        if value.strip()
    ]
    if configured:
        return list(dict.fromkeys(configured))
    if is_production():
        return []
    return ["http://localhost:5173", "http://127.0.0.1:5173"]


def validate_production_config() -> None:
    if not is_production():
        return

    errors = []
    secret_key = os.getenv("SECRET_KEY", "")
    password_hash = os.getenv("ADMIN_PASSWORD_HASH", "")
    origins = cors_origins()

    if DATABASE_URL.startswith("sqlite") or not DATABASE_URL:
        errors.append("DATABASE_URL must use production Postgres")
    if len(secret_key) < 32 or secret_key == "change-this-in-production":
        errors.append("SECRET_KEY must be a unique value of at least 32 characters")
    if not password_hash.startswith(("$2a$", "$2b$", "$2y$")):
        errors.append("ADMIN_PASSWORD_HASH must contain a bcrypt hash, not a plain password")
    if not origins or "*" in origins:
        errors.append("CORS_ORIGINS must contain the deployed Vercel URL and cannot use '*'")
    for origin in origins:
        parsed = urlparse(origin)
        if parsed.scheme != "https" or not parsed.netloc:
            errors.append(f"CORS origin must be a complete HTTPS URL: {origin}")
    if not cloudinary_is_configured():
        errors.append("Cloudinary credentials are required for permanent production uploads")
    if not email_is_configured():
        errors.append("RESEND_API_KEY and EMAIL_FROM are required in production")
    if os.getenv("AUTOMATION_ENABLED", "").casefold() in ("1", "true", "yes"):
        if len(os.getenv("CRON_SECRET", "")) < 24:
            errors.append("CRON_SECRET must be at least 24 characters when automation is enabled")

    if errors:
        message = "\n - ".join(errors)
        raise RuntimeError(f"Production configuration is incomplete:\n - {message}")
