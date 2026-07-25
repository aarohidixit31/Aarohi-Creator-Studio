import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import models
from app.auth import get_current_admin
from app.database import Base, get_db
from app.main import app
from app.routers import collabs, media_kit


TEST_ENGINE = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=TEST_ENGINE,
)


def override_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture()
def db():
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def client(monkeypatch):
    Base.metadata.drop_all(bind=TEST_ENGINE)
    Base.metadata.create_all(bind=TEST_ENGINE)
    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_admin] = lambda: "admin@test.local"
    monkeypatch.setattr(collabs, "send_inquiry_notifications", lambda *args, **kwargs: None)
    monkeypatch.setattr(media_kit, "refresh_stale_stats", lambda: None)

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


@pytest.fixture()
def seed_brand(client, db):
    brand = models.Brand(
        name="Notion",
        contact_person="Maya",
        email="maya@notion.com",
        phone="+91 90000 00000",
    )
    db.add(brand)
    db.commit()
    db.refresh(brand)
    return brand
