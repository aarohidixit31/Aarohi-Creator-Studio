from datetime import datetime, timedelta, timezone

from app import models
from app.routers import automation
from app.services.email import EmailResult


def test_daily_automation_sends_due_invoice_and_manager_digest(
    client,
    db,
    seed_brand,
    monkeypatch,
):
    monkeypatch.setenv("AUTOMATION_ENABLED", "true")
    monkeypatch.setenv("CRON_SECRET", "test-cron-secret")
    monkeypatch.setenv("INVOICE_REMINDER_INTERVAL_DAYS", "3")

    invoice_data = client.post("/api/invoices/", json={
        "brand_id": seed_brand.id,
        "line_items": [{"description": "Instagram Reel", "quantity": 1, "rate": 9000}],
    }).json()
    invoice = db.query(models.Invoice).filter(models.Invoice.id == invoice_data["id"]).first()
    invoice.status = "sent"
    invoice.due_date = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=2)

    collab_data = client.post("/api/collabs/", json={
        "brand_id": seed_brand.id,
        "status": "new_inquiry",
        "campaign_type": "Instagram Reel",
    }).json()
    collab = db.query(models.Collab).filter(models.Collab.id == collab_data["id"]).first()
    collab.created_at = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=3)
    db.commit()

    invoice_deliveries = []
    digests = []
    monkeypatch.setattr(automation, "_render_invoice_pdf", lambda *args, **kwargs: b"%PDF-auto")

    def fake_invoice_delivery(payload, pdf_bytes, **kwargs):
        invoice_deliveries.append({"payload": payload, "pdf": pdf_bytes, **kwargs})
        return EmailResult(payload["recipient"], True, message_id="auto-email-1")

    def fake_digest(items, idempotency_key):
        digests.append({"items": items, "idempotency_key": idempotency_key})
        return EmailResult("manager@test.local", True, message_id="digest-1")

    monkeypatch.setattr(automation.email_service, "send_invoice_delivery", fake_invoice_delivery)
    monkeypatch.setattr(automation.email_service, "send_manager_attention_digest", fake_digest)

    response = client.post("/api/automation/run")
    assert response.status_code == 200
    result = response.json()
    assert result["invoice_reminders_sent"] == 1
    assert result["collaboration_follow_ups"] == 1
    assert result["manager_digest_sent"] is True
    assert invoice_deliveries[0]["reminder"] is True
    assert invoice_deliveries[0]["pdf"] == b"%PDF-auto"
    assert digests[0]["items"][0]["brand_name"] == "Notion"

    db.refresh(invoice)
    assert invoice.status == "overdue"
    assert invoice.reminder_count == 1
    assert invoice.last_reminded_at is not None

    invalid_cron = client.post(
        "/api/automation/cron",
        headers={"X-Cron-Secret": "wrong"},
    )
    assert invalid_cron.status_code == 401

    valid_cron = client.post(
        "/api/automation/cron",
        headers={"X-Cron-Secret": "test-cron-secret"},
    )
    assert valid_cron.status_code == 200
    assert valid_cron.json()["invoice_reminders_sent"] == 0
