from datetime import datetime, timezone

from app import models


def test_calendar_combines_manager_dates_and_excludes_archived_collabs(client, db, seed_brand):
    event_date = datetime(2026, 8, 20, 10, 30, tzinfo=timezone.utc)
    collab = models.Collab(
        brand_id=seed_brand.id,
        status="confirmed",
        campaign_type="Product launch",
        deadline=event_date,
        details={"follow_up_at": "2026-08-18T09:00:00+00:00", "next_action": "Approve script"},
    )
    archived = models.Collab(
        brand_id=seed_brand.id,
        status="confirmed",
        deadline=event_date,
        archived_at=datetime(2026, 8, 1, tzinfo=timezone.utc),
    )
    db.add_all([collab, archived])
    db.flush()
    db.add(models.Invoice(
        brand_id=seed_brand.id,
        collab_id=collab.id,
        invoice_number="INV-CALENDAR-001",
        line_items=[{"description": "Launch", "quantity": 1, "rate": 20000}],
        subtotal=20000,
        total=20000,
        due_date=datetime(2026, 8, 25, tzinfo=timezone.utc),
        status="sent",
    ))
    db.add(models.ContentItem(
        brand_id=seed_brand.id,
        collab_id=collab.id,
        platform="Instagram",
        title="Launch Reel",
        published_at=datetime(2026, 8, 28, tzinfo=timezone.utc),
    ))
    db.commit()

    response = client.get(
        "/api/calendar/?start=2026-08-01T00:00:00Z&end=2026-09-01T00:00:00Z"
    )

    assert response.status_code == 200
    events = response.json()["events"]
    assert [event["type"] for event in events] == ["follow_up", "deadline", "invoice", "content"]
    assert sum(event["type"] == "deadline" for event in events) == 1
    assert next(event for event in events if event["type"] == "invoice")["amount"] == 20000


def test_calendar_rejects_invalid_or_excessive_ranges(client):
    backwards = client.get(
        "/api/calendar/?start=2026-09-01T00:00:00Z&end=2026-08-01T00:00:00Z"
    )
    too_wide = client.get(
        "/api/calendar/?start=2026-01-01T00:00:00Z&end=2026-12-31T00:00:00Z"
    )

    assert backwards.status_code == 400
    assert too_wide.status_code == 400
