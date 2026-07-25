import os

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
