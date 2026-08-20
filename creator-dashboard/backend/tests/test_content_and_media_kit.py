def test_media_kit_update_and_public_read(client):
    updated = client.put("/api/media-kit/", json={
        "name": "Aarohi Dixit",
        "tagline": "Tech Content Creator",
        "bio": "Making technology practical and approachable.",
        "social_links": [{
            "platform": "YouTube",
            "label": "YouTube",
            "handle": "@aarohi.inframe",
            "url": "https://youtube.com/@aarohi.inframe",
            "follower_count": 350,
            "secondary_stat": "Manual fallback",
        }],
        "content_pillars": ["AI tools", "Coding", "Career"],
    })
    assert updated.status_code == 200

    public = client.get("/api/media-kit/")
    assert public.status_code == 200
    assert public.json()["bio"].startswith("Making technology")
    assert public.json()["social_links"][0]["follower_count"] == 350
    assert public.json()["content_pillars"] == ["AI tools", "Coding", "Career"]


def test_media_kit_draft_preview_publish_and_visibility(client):
    client.put("/api/media-kit/", json={
        "bio": "Currently public",
        "rate_card": [{"deliverable": "Instagram Reel", "price": 8000}],
    })

    saved = client.put("/api/media-kit/draft", json={
        "bio": "Approved draft copy",
        "portrait_style": "cutout",
        "rate_card": [
            {"deliverable": "Instagram Reel", "price": 9000, "visible": True},
            {"deliverable": "Private package", "price": 15000, "visible": False},
        ],
        "section_order": ["services", "proof"],
        "hidden_sections": ["testimonials"],
    })
    assert saved.status_code == 200
    assert saved.json()["publication"]["has_draft"] is True

    # Saving a working copy must never change what a brand can see.
    assert client.get("/api/media-kit/").json()["bio"] == "Currently public"
    draft = client.get("/api/media-kit/draft").json()
    assert draft["bio"] == "Approved draft copy"
    assert draft["portrait_style"] == "cutout"
    assert draft["rate_card"][1]["visible"] is False

    published = client.post("/api/media-kit/publish")
    assert published.status_code == 200
    assert published.json()["publication"]["published_by"] == "admin@test.local"

    public = client.get("/api/media-kit/").json()
    assert public["bio"] == "Approved draft copy"
    assert public["portrait_style"] == "cutout"
    assert [item["deliverable"] for item in public["rate_card"]] == ["Instagram Reel"]
    assert public["section_order"][:2] == ["services", "proof"]
    assert public["hidden_sections"] == ["testimonials"]


def test_content_crud_summary_and_public_case_study(client, seed_brand):
    collab = client.post("/api/collabs/", json={
        "brand_id": seed_brand.id,
        "status": "content_posted",
        "campaign_type": "Instagram Reel",
    }).json()
    created = client.post("/api/content/", json={
        "brand_id": seed_brand.id,
        "collab_id": collab["id"],
        "platform": "Instagram",
        "title": "AI workflow for students",
        "content_url": "https://instagram.com/p/example",
        "objective": "Introduce a productivity tool",
        "results": "Exceeded the campaign reach target.",
        "metrics": {
            "views": 125000,
            "reach": 98000,
            "likes": 7400,
            "comments": 210,
            "saves": 1800,
            "shares": 950,
            "engagement_rate": 7.4,
        },
        "featured": True,
    })
    assert created.status_code == 201
    item = created.json()
    assert item["brand"]["name"] == "Notion"
    assert item["collab_label"] == "Instagram Reel"

    summary = client.get("/api/content/summary").json()
    assert summary["content_count"] == 1
    assert summary["total_views"] == 125000
    assert summary["featured_count"] == 1

    public = client.get("/api/content/case-studies")
    assert public.status_code == 200
    assert public.json()[0]["title"] == "AI workflow for students"

    changed = client.patch(f"/api/content/{item['id']}", json={
        "platform": "YouTube",
        "featured": False,
    })
    assert changed.status_code == 200
    assert changed.json()["platform"] == "YouTube"
    assert client.get("/api/content/case-studies").json() == []

    removed = client.delete(f"/api/content/{item['id']}")
    assert removed.status_code == 204
    assert client.get("/api/content/summary").json()["content_count"] == 0


def test_content_performance_scoring_proof_and_public_privacy(client, seed_brand):
    base = {
        "brand_id": seed_brand.id,
        "platform": "Instagram",
        "content_url": "https://instagram.com/reel/example",
        "featured": True,
    }
    first = client.post("/api/content/", json={
        **base,
        "title": "Baseline reel",
        "notes": "Private manager context",
        "metrics": {
            "views": 10000,
            "reach": 8000,
            "likes": 500,
            "comments": 50,
        },
    })
    assert first.status_code == 201

    breakout = client.post("/api/content/", json={
        **base,
        "title": "High-performing reel",
        "notes": "Do not expose this note",
        "metrics": {
            "views": 30000,
            "reach": 24000,
            "likes": 2400,
            "comments": 180,
            "saves": 600,
            "shares": 420,
            "verification_method": "screenshot",
            "proof_url": "https://res.cloudinary.com/example/analytics-proof.png",
        },
    })
    assert breakout.status_code == 201

    records = client.get("/api/content/").json()
    high = next(item for item in records if item["title"] == "High-performing reel")
    low = next(item for item in records if item["title"] == "Baseline reel")
    assert high["performance_score"] > low["performance_score"]
    assert high["performance_multiplier"] == 1.5
    assert high["performance_label"] == "High performer"
    assert high["calculated_engagement_rate"] == 15.0
    assert high["metrics"]["measured_at"] is not None

    summary = client.get("/api/content/summary").json()
    assert summary["high_performer_count"] == 1
    assert summary["verified_count"] == 1
    assert summary["top_content_id"] == high["id"]

    public = client.get("/api/content/case-studies").json()
    assert public[0]["title"] == "High-performing reel"
    assert public[0]["notes"] is None
    assert public[0]["metrics"].get("proof_url") is None


def test_content_rejects_unknown_metric_verification_source(client):
    response = client.post("/api/content/", json={
        "platform": "Instagram",
        "title": "Untrusted metrics",
        "metrics": {"views": 100, "verification_method": "spreadsheet"},
    })
    assert response.status_code == 400
    assert "verification" in response.json()["detail"].lower()


def test_youtube_content_sync_imports_updates_and_queues_review(client, monkeypatch):
    from app.services import content_sync

    monkeypatch.setenv("YOUTUBE_API_KEY", "test-key")
    monkeypatch.setenv("YOUTUBE_HANDLE", "@aarohi.inframe")
    monkeypatch.delenv("YOUTUBE_CHANNEL_ID", raising=False)
    current_views = {"video-one": "12000", "video-two": "36000"}

    def fake_get(url):
        if "/channels?" in url:
            return {"items": [{"contentDetails": {"relatedPlaylists": {"uploads": "UU123"}}}]}
        if "/playlistItems?" in url:
            return {"items": [
                {"contentDetails": {"videoId": "video-one"}},
                {"contentDetails": {"videoId": "video-two"}},
            ]}
        if "/videos?" in url:
            return {"items": [
                {
                    "id": video_id,
                    "snippet": {
                        "title": f"Title for {video_id}",
                        "publishedAt": "2026-08-01T10:00:00Z",
                        "thumbnails": {"high": {"url": f"https://img.youtube.com/{video_id}.jpg"}},
                    },
                    "statistics": {"viewCount": current_views[video_id], "likeCount": "500", "commentCount": "25"},
                    "contentDetails": {"duration": "PT1M30S"},
                    "status": {"privacyStatus": "public"},
                }
                for video_id in ("video-one", "video-two") if video_id in url
            ]}
        raise AssertionError(f"Unexpected URL: {url}")

    monkeypatch.setattr(content_sync, "_get_json", fake_get)
    monkeypatch.setattr(content_sync, "connection_status", lambda db: {
        "configured": True,
        "connected": True,
        "account_id": "UC123",
        "account_name": "Aarohi Inframe",
        "scopes": [],
        "expires_at": None,
    })
    monkeypatch.setattr(content_sync, "video_analytics", lambda db, ids: {
        video_id: {
            "averageViewDuration": 18.5,
            "averageViewPercentage": 61.2,
            "estimatedMinutesWatched": 4200,
            "subscribersGained": 17,
            "shares": 88,
        }
        for video_id in ids
    })
    catalog = client.get("/api/content/youtube/catalog")
    assert catalog.status_code == 200
    assert [item["video_id"] for item in catalog.json()["items"]] == ["video-one", "video-two"]
    assert not any(item["already_imported"] for item in catalog.json()["items"])

    first = client.post("/api/content/youtube/import", json={"video_ids": ["video-two"]})
    assert first.status_code == 200
    assert first.json()["imported"] == 1
    assert first.json()["updated"] == 0
    assert first.json()["pending_review"] == 1
    assert first.json()["analytics_connected"] is True

    records = client.get("/api/content/").json()
    assert len(records) == 1
    assert records[0]["metrics"]["external_id"] == "video-two"
    assert records[0]["metrics"]["average_watch_time_seconds"] == 18.5
    assert records[0]["metrics"]["average_view_percentage"] == 61.2
    assert records[0]["metrics"]["estimated_minutes_watched"] == 4200
    assert records[0]["metrics"]["follows"] == 17
    assert records[0]["metrics"]["shares"] == 88
    assert all(item["featured"] is False for item in records)
    assert all(item["metrics"]["verification_method"] == "api" for item in records)
    assert all(item["metrics"]["review_status"] == "pending" for item in records)
    assert all(item["metrics"]["duration_seconds"] == 90 for item in records)
    assert client.get("/api/content/case-studies").json() == []

    current_views["video-two"] = "39000"
    second = client.post("/api/content/youtube/import", json={"video_ids": ["video-two"]})
    assert second.status_code == 200
    assert second.json()["imported"] == 0
    assert second.json()["updated"] == 1
    records = client.get("/api/content/").json()
    assert len(records) == 1
    assert records[0]["metrics"]["views"] == 39000

    catalog = client.get("/api/content/youtube/catalog").json()
    states = {item["video_id"]: item["already_imported"] for item in catalog["items"]}
    assert states == {"video-one": False, "video-two": True}

    summary = client.get("/api/content/summary").json()
    assert summary["imported_count"] == 1
    assert summary["pending_review_count"] == 1


def test_youtube_content_sync_requires_configuration(client, monkeypatch):
    monkeypatch.delenv("YOUTUBE_API_KEY", raising=False)
    monkeypatch.delenv("YOUTUBE_CHANNEL_ID", raising=False)
    monkeypatch.delenv("YOUTUBE_HANDLE", raising=False)
    response = client.get("/api/content/youtube/catalog")
    assert response.status_code == 400
    assert "YOUTUBE_API_KEY" in response.json()["detail"]


def test_instagram_selective_import_and_insights_refresh(client, monkeypatch):
    from app.services import instagram_content_sync

    monkeypatch.setenv("META_ACCESS_TOKEN", "instagram-token")
    monkeypatch.setenv("INSTAGRAM_ACCOUNT_ID", "ig-account")
    media = [
        {
            "id": "reel-one",
            "caption": "First Reel\nMore caption",
            "media_type": "VIDEO",
            "media_product_type": "REELS",
            "permalink": "https://instagram.com/reel/one/",
            "thumbnail_url": "https://images.example/reel-one.jpg",
            "timestamp": "2026-08-01T10:00:00Z",
            "like_count": 120,
            "comments_count": 8,
        },
        {
            "id": "post-two",
            "caption": "Carousel campaign",
            "media_type": "CAROUSEL_ALBUM",
            "media_product_type": "FEED",
            "permalink": "https://instagram.com/p/two/",
            "media_url": "https://images.example/post-two.jpg",
            "timestamp": "2026-08-02T10:00:00Z",
            "like_count": 80,
            "comments_count": 5,
        },
    ]
    insight_values = {
        "views": 24000,
        "reach": 19000,
        "saved": 420,
        "shares": 310,
        "total_interactions": 980,
        "follows": 37,
        "profile_visits": 160,
        "ig_reels_avg_watch_time": 18500,
    }

    def fake_graph_get(db, path, params=None):
        if path.endswith("/media"):
            return {"data": media}
        metric = (params or {}).get("metric")
        value = insight_values.get(metric)
        return {"data": []} if value is None else {"data": [{"name": metric, "values": [{"value": value}]}]}

    monkeypatch.setattr(instagram_content_sync, "graph_get", fake_graph_get)
    catalog = client.get("/api/content/instagram/catalog")
    assert catalog.status_code == 200
    assert catalog.json()["oauth"]["connection_type"] == "environment"
    assert [item["media_id"] for item in catalog.json()["items"]] == ["reel-one", "post-two"]

    imported = client.post("/api/content/instagram/import", json={"media_ids": ["reel-one"]})
    assert imported.status_code == 200
    assert imported.json()["imported"] == 1
    records = client.get("/api/content/").json()
    assert len(records) == 1
    record = records[0]
    assert record["title"] == "First Reel"
    assert record["metrics"]["external_id"] == "reel-one"
    assert record["metrics"]["views"] == 24000
    assert record["metrics"]["reach"] == 19000
    assert record["metrics"]["saves"] == 420
    assert record["metrics"]["shares"] == 310
    assert record["metrics"]["average_watch_time_seconds"] == 18.5
    assert record["metrics"]["media_product_type"] == "REELS"
    assert record["featured"] is False

    catalog = client.get("/api/content/instagram/catalog").json()
    states = {item["media_id"]: item["already_imported"] for item in catalog["items"]}
    assert states == {"reel-one": True, "post-two": False}

    insight_values["views"] = 26000
    refreshed = client.post("/api/content/instagram/refresh")
    assert refreshed.status_code == 200
    assert refreshed.json()["updated"] == 1
    assert client.get("/api/content/").json()[0]["metrics"]["views"] == 26000
