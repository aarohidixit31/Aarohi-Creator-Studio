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
    assert draft["rate_card"][1]["visible"] is False

    published = client.post("/api/media-kit/publish")
    assert published.status_code == 200
    assert published.json()["publication"]["published_by"] == "admin@test.local"

    public = client.get("/api/media-kit/").json()
    assert public["bio"] == "Approved draft copy"
    assert [item["deliverable"] for item in public["rate_card"]] == ["Instagram Reel"]
    assert public["section_order"][:2] == ["services", "proof"]
    assert public["hidden_sections"] == ["testimonials"]


def test_content_crud_summary_and_public_case_study(client, seed_brand):
    collab = client.post("/api/collabs/", json={
        "brand_id": seed_brand.id,
        "status": "content_live",
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
