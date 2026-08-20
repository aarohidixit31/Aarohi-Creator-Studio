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


def test_calendar_notes_can_be_created_updated_listed_and_deleted(client):
    created = client.put(
        "/api/calendar/notes/2026-08-19",
        json={"content": "Call the brand and review tomorrow's shot list."},
    )
    assert created.status_code == 200
    assert created.json()["note_date"] == "2026-08-19"

    updated = client.put(
        "/api/calendar/notes/2026-08-19",
        json={"content": "Call moved to 4 PM."},
    )
    assert updated.status_code == 200
    assert updated.json()["content"] == "Call moved to 4 PM."

    calendar = client.get(
        "/api/calendar/?start=2026-08-01T00:00:00Z&end=2026-09-01T00:00:00Z"
    )
    assert calendar.status_code == 200
    assert calendar.json()["notes"] == [updated.json()]

    deleted = client.delete("/api/calendar/notes/2026-08-19")
    assert deleted.status_code == 204
    calendar = client.get(
        "/api/calendar/?start=2026-08-01T00:00:00Z&end=2026-09-01T00:00:00Z"
    )
    assert calendar.json()["notes"] == []


def test_completed_collab_replaces_deadline_with_status_milestone(client, db, seed_brand):
    collab = models.Collab(
        brand_id=seed_brand.id,
        status="content_posted",
        campaign_type="Launch Reel",
        deadline=datetime(2026, 8, 20, 10, 30, tzinfo=timezone.utc),
        details={
            "activity_log": [{
                "timestamp": "2026-08-18T12:00:00+00:00",
                "action": "status_changed",
                "detail": "Moved to content posted",
                "from_status": "draft_submitted",
                "to_status": "content_posted",
            }],
        },
    )
    db.add(collab)
    db.commit()

    response = client.get(
        "/api/calendar/?start=2026-08-01T00:00:00Z&end=2026-09-01T00:00:00Z"
    )
    events = response.json()["events"]

    assert not any(event["type"] == "deadline" for event in events)
    milestone = next(event for event in events if event["key"].startswith("status-"))
    assert milestone["title"] == "Content posted"
    assert milestone["type"] == "content"
