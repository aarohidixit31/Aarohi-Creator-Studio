import pytest

from app import config
from app.services.storage import store_image


def test_development_cors_defaults_are_local_only(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.delenv("CORS_ORIGINS", raising=False)
    assert config.cors_origins() == [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]


def test_production_config_fails_closed(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("CORS_ORIGINS", "*")
    monkeypatch.setenv("SECRET_KEY", "short")
    monkeypatch.setenv("ADMIN_PASSWORD_HASH", "plain-password")
    monkeypatch.setattr(config, "DATABASE_URL", "sqlite:///unsafe.db")
    monkeypatch.setattr(config, "cloudinary_is_configured", lambda: False)
    monkeypatch.setattr(config, "email_is_configured", lambda: False)

    with pytest.raises(RuntimeError) as exc:
        config.validate_production_config()

    message = str(exc.value)
    assert "production Postgres" in message
    assert "bcrypt hash" in message
    assert "cannot use '*'" in message
    assert "Cloudinary" in message


def test_local_storage_fallback_and_production_guard(tmp_path, monkeypatch):
    for name in ("CLOUDINARY_CLOUD_NAME", "CLOUDINARY_API_KEY", "CLOUDINARY_API_SECRET"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("ENVIRONMENT", "development")

    result = store_image(
        b"test-image-bytes",
        original_filename="test.webp",
        content_type="image/webp",
        local_directory=tmp_path,
        local_url_prefix="/api/uploads/media-kit",
        local_extension=".webp",
    )
    assert result.backend == "local"
    assert result.url.startswith("/api/uploads/media-kit/")
    assert len(list(tmp_path.iterdir())) == 1

    monkeypatch.setenv("ENVIRONMENT", "production")
    with pytest.raises(RuntimeError, match="Cloudinary is required"):
        store_image(
            b"test-image-bytes",
            original_filename="test.webp",
            content_type="image/webp",
            local_directory=tmp_path,
            local_url_prefix="/api/uploads/media-kit",
            local_extension=".webp",
        )
