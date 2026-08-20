import os
from urllib.parse import parse_qs, urlparse

from app import models
from app.auth import create_access_token, get_current_admin
from app.services import social_stats


def test_jwt_round_trip():
    token = create_access_token()
    assert get_current_admin(token) == os.getenv("ADMIN_EMAIL", "you@example.com")


def test_protected_route_rejects_missing_token(client):
    from app.auth import get_current_admin as auth_dependency
    from app.main import app

    override = app.dependency_overrides.pop(auth_dependency)
    try:
        response = client.get("/api/brands/")
        assert response.status_code == 401
    finally:
        app.dependency_overrides[auth_dependency] = override


def test_social_stats_refresh_cache_and_media_kit_merge(client, db, monkeypatch):
    monkeypatch.setenv("YOUTUBE_API_KEY", "test-key")
    monkeypatch.setenv("YOUTUBE_HANDLE", "@aarohi.inframe")
    monkeypatch.delenv("YOUTUBE_CHANNEL_ID", raising=False)
    monkeypatch.setenv("META_ACCESS_TOKEN", "test-token")
    monkeypatch.setenv("INSTAGRAM_ACCOUNT_ID", "17840000000000000")

    calls = []

    def fake_get(url):
        calls.append(url)
        if "googleapis" in url:
            return {
                "items": [{
                    "id": "UC123",
                    "snippet": {"title": "Aarohi Inframe"},
                    "statistics": {
                        "subscriberCount": "432",
                        "viewCount": "125000",
                        "videoCount": "18",
                        "hiddenSubscriberCount": False,
                    },
                }],
            }
        return {
            "id": "1784",
            "username": "aarohi.inframe",
            "followers_count": 25360,
            "media_count": 210,
        }

    monkeypatch.setattr(social_stats, "_get_json", fake_get)
    refreshed = client.post("/api/social-stats/refresh?platform=all")
    assert refreshed.status_code == 200
    assert len(calls) == 2
    values = {item["platform"]: item for item in refreshed.json()}
    assert values["youtube"]["data"]["total_views"] == 125000
    assert values["instagram"]["data"]["followers"] == 25360
    history = client.get("/api/social-stats/history?days=30")
    assert history.status_code == 200
    snapshots = {item["platform"]: item for item in history.json()}
    assert snapshots["youtube"]["followers"] == 432
    assert snapshots["youtube"]["total_views"] == 125000
    assert snapshots["instagram"]["followers"] == 25360

    client.put("/api/media-kit/", json={
        "social_links": [
            {
                "platform": "YouTube",
                "label": "YouTube",
                "handle": "@aarohi.inframe",
                "url": "https://youtube.com/@aarohi.inframe",
                "follower_count": 1,
            },
            {
                "platform": "Instagram",
                "label": "Instagram",
                "handle": "@aarohi.inframe",
                "url": "https://instagram.com/aarohi.inframe",
                "follower_count": 1,
            },
        ],
    })
    public = client.get("/api/media-kit/").json()
    socials = {item["platform"]: item for item in public["social_links"]}
    assert socials["YouTube"]["follower_count"] == 432
    assert socials["Instagram"]["follower_count"] == 25360
    assert socials["YouTube"]["live"] is True

    social_stats.refresh_platform(db, "youtube", force=False)
    social_stats.refresh_platform(db, "instagram", force=False)
    assert len(calls) == 2


def test_youtube_oauth_connection_flow(client, db, monkeypatch):
    from app.services import youtube_oauth

    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_ID", "google-client")
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_SECRET", "google-secret")
    monkeypatch.setenv("GOOGLE_OAUTH_REDIRECT_URI", "https://api.example.com/api/youtube/oauth/callback")
    monkeypatch.setenv("FRONTEND_URL", "https://studio.example.com")

    def fake_request(url, *, data=None, token=None):
        if url == "https://oauth2.googleapis.com/token":
            return {
                "access_token": "access-value",
                "refresh_token": "refresh-value",
                "expires_in": 3600,
                "scope": " ".join(youtube_oauth.SCOPES),
            }
        if "youtube/v3/channels" in url:
            assert token == "access-value"
            return {"items": [{"id": "UC123", "snippet": {"title": "Aarohi Inframe"}}]}
        raise AssertionError(f"Unexpected OAuth request: {url}")

    monkeypatch.setattr(youtube_oauth, "_request_json", fake_request)
    started = client.get("/api/youtube/oauth/start")
    assert started.status_code == 200
    authorization_url = started.json()["authorization_url"]
    query = parse_qs(urlparse(authorization_url).query)
    assert query["access_type"] == ["offline"]
    assert set(query["scope"][0].split()) == set(youtube_oauth.SCOPES)

    callback = client.get(
        "/api/youtube/oauth/callback",
        params={"code": "authorization-code", "state": query["state"][0]},
        follow_redirects=False,
    )
    assert callback.status_code in (302, 307)
    assert callback.headers["location"] == "https://studio.example.com/admin/content?youtube=connected"

    status = client.get("/api/youtube/oauth/status").json()
    assert status["connected"] is True
    assert status["account_name"] == "Aarohi Inframe"
    saved = db.query(models.OAuthConnection).filter_by(provider="youtube").one()
    assert saved.access_token != "access-value"
    assert saved.refresh_token != "refresh-value"

    disconnected = client.delete("/api/youtube/oauth/connection")
    assert disconnected.status_code == 204
    assert client.get("/api/youtube/oauth/status").json()["connected"] is False


def test_instagram_oauth_connection_flow(client, db, monkeypatch):
    from app.services import instagram_oauth

    monkeypatch.delenv("META_ACCESS_TOKEN", raising=False)
    monkeypatch.delenv("INSTAGRAM_ACCOUNT_ID", raising=False)
    monkeypatch.setenv("META_APP_ID", "meta-app")
    monkeypatch.setenv("META_APP_SECRET", "meta-secret")
    monkeypatch.setenv("META_LOGIN_CONFIG_ID", "login-config")
    monkeypatch.setenv("META_OAUTH_REDIRECT_URI", "http://localhost:8000/api/instagram/oauth/callback")
    monkeypatch.setenv("FRONTEND_URL", "http://localhost:5173")

    def fake_request(url, *, data=None, token=None):
        if "graph.facebook.com" in url and "/oauth/access_token?" in url and "code=" in url:
            return {"access_token": "short-token", "expires_in": 3600}
        if "graph.facebook.com" in url and "fb_exchange_token=" in url:
            return {"access_token": "long-user-token", "expires_in": 5184000}
        if "/me/accounts?" in url:
            assert token == "long-user-token"
            return {"data": [{
                "id": "page-123",
                "name": "Aarohi Inframe",
                "access_token": "page-token",
                "instagram_business_account": {
                    "id": "ig-123",
                    "username": "aarohi.inframe",
                    "followers_count": 25000,
                },
            }]}
        raise AssertionError(f"Unexpected Instagram request: {url}")

    monkeypatch.setattr(instagram_oauth, "_request_json", fake_request)
    started = client.get("/api/instagram/oauth/start")
    assert started.status_code == 200
    query = parse_qs(urlparse(started.json()["authorization_url"]).query)
    assert query["config_id"] == ["login-config"]
    assert "scope" not in query
    assert query["override_default_response_type"] == ["true"]

    callback = client.get(
        "/api/instagram/oauth/callback",
        params={"code": "instagram-code", "state": query["state"][0]},
        follow_redirects=False,
    )
    assert callback.status_code in (302, 307)
    assert callback.headers["location"] == "http://localhost:5173/admin/content?instagram=connected"
    status = client.get("/api/instagram/oauth/status").json()
    assert status["connected"] is True
    assert status["account_name"] == "aarohi.inframe"
    assert status["connection_type"] == "oauth"
    saved = db.query(models.OAuthConnection).filter_by(provider="instagram").one()
    assert saved.access_token != "page-token"

    assert client.delete("/api/instagram/oauth/connection").status_code == 204
    assert client.get("/api/instagram/oauth/status").json()["connected"] is False


def test_direct_instagram_oauth_without_facebook_page(client, db, monkeypatch):
    from app.services import instagram_oauth

    monkeypatch.setenv("INSTAGRAM_AUTH_MODE", "instagram")
    monkeypatch.setenv("INSTAGRAM_APP_ID", "instagram-app")
    monkeypatch.setenv("INSTAGRAM_APP_SECRET", "instagram-secret")
    monkeypatch.setenv("INSTAGRAM_OAUTH_REDIRECT_URI", "http://localhost:8000/api/instagram/oauth/callback")
    monkeypatch.setenv("FRONTEND_URL", "http://localhost:5173")
    monkeypatch.delenv("META_ACCESS_TOKEN", raising=False)
    monkeypatch.delenv("INSTAGRAM_ACCOUNT_ID", raising=False)

    def fake_request(url, *, data=None, token=None):
        if url == "https://api.instagram.com/oauth/access_token":
            return {"access_token": "short-instagram-token", "user_id": "ig-direct-123"}
        if url.startswith("https://graph.instagram.com/access_token?"):
            return {"access_token": "long-instagram-token", "expires_in": 5184000}
        if "/ig-direct-123?fields=" in url:
            assert token == "long-instagram-token"
            return {"id": "ig-direct-123", "username": "aarohi.inframe"}
        raise AssertionError(f"Unexpected direct Instagram request: {url}")

    monkeypatch.setattr(instagram_oauth, "_request_json", fake_request)
    started = client.get("/api/instagram/oauth/start")
    assert started.status_code == 200
    parsed = urlparse(started.json()["authorization_url"])
    query = parse_qs(parsed.query)
    assert parsed.netloc == "www.instagram.com"
    assert set(query["scope"][0].split(",")) == set(instagram_oauth.INSTAGRAM_SCOPES)

    callback = client.get(
        "/api/instagram/oauth/callback",
        params={"code": "instagram-code", "state": query["state"][0]},
        follow_redirects=False,
    )
    assert callback.headers["location"] == "http://localhost:5173/admin/content?instagram=connected"
    status = client.get("/api/instagram/oauth/status").json()
    assert status["connected"] is True
    assert status["account_name"] == "aarohi.inframe"
    saved = db.query(models.OAuthConnection).filter_by(provider="instagram").one()
    assert "instagram_business_basic" in saved.scopes
    assert saved.access_token != "long-instagram-token"
