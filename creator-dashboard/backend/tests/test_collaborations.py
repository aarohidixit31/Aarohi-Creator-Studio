from datetime import datetime, timedelta, timezone

from app import models


def inquiry_payload(email="partner@acme.com"):
    return {
        "brand_name": "Acme",
        "contact_person": "Riya",
        "email": email,
        "phone": "+91 98765 43210",
        "budget": 25000,
        "campaign_type": "Instagram Reel, YouTube Short",
        "deliverables": "1 Reel + 2 Stories",
        "brief": None,
    }


def test_public_inquiry_reuses_brand_by_email(client, db):
    first = client.post("/api/collabs/inquiry", json=inquiry_payload())
    second = client.post("/api/collabs/inquiry", json=inquiry_payload("PARTNER@ACME.COM"))

    assert first.status_code == 201
    assert first.json()["brand_reused"] is False
    assert second.status_code == 201
    assert second.json()["brand_reused"] is True
    assert second.json()["brand_id"] == first.json()["brand_id"]
    assert db.query(models.Brand).count() == 1
    assert db.query(models.Collab).count() == 2


def test_admin_can_create_and_manage_collaboration(client, seed_brand):
    created = client.post("/api/collabs/", json={
        "brand_id": seed_brand.id,
        "status": "confirmed",
        "campaign_type": "Product launch",
        "deliverables": "1 Reel",
        "budget": 30000,
    })
    assert created.status_code == 201
    collab_id = created.json()["id"]

    follow_up = datetime.now(timezone.utc) + timedelta(days=2)
    updated = client.patch(f"/api/collabs/{collab_id}", json={
        "follow_up_at": follow_up.isoformat(),
        "deliverable_checklist": [
            {"text": "Approve script", "completed": True},
            {"text": "Publish reel", "completed": False},
        ],
        "notes": "Brand prefers concise technical demos.",
    })
    assert updated.status_code == 200
    assert len(updated.json()["deliverable_checklist"]) == 2
    assert updated.json()["notes"].startswith("Brand prefers")

    moved = client.patch(f"/api/collabs/{collab_id}/status", json={"status": "content_live"})
    assert moved.status_code == 200
    detail = client.get(f"/api/collabs/{collab_id}")
    assert detail.json()["status"] == "content_live"
    assert any(event["action"] == "status_changed" for event in detail.json()["activity_log"])


def test_attention_queue_combines_followups_deadlines_and_payments(client, seed_brand):
    past = datetime.now(timezone.utc) - timedelta(days=2)
    collab = client.post("/api/collabs/", json={
        "brand_id": seed_brand.id,
        "status": "new_inquiry",
        "campaign_type": "Launch Reel",
        "deadline": past.isoformat(),
    }).json()
    client.patch(f"/api/collabs/{collab['id']}", json={"follow_up_at": past.isoformat()})

    invoice = client.post("/api/invoices/", json={
        "brand_id": seed_brand.id,
        "collab_id": collab["id"],
        "line_items": [{"description": "Launch Reel", "quantity": 1, "rate": 25000}],
        "tax_percent": 0,
        "due_date": past.isoformat(),
    }).json()
    client.patch(f"/api/invoices/{invoice['id']}/status?status=sent")

    queue = client.get("/api/collabs/attention")
    assert queue.status_code == 200
    types = [item["type"] for item in queue.json()["items"]]
    assert {"inquiry", "follow_up", "deadline", "payment"}.issubset(types)
    assert queue.json()["summary"]["urgent"] >= 3
