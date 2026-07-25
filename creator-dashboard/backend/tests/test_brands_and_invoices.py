from datetime import datetime, timedelta, timezone

from app.routers import invoices as invoice_router
from app.services.email import EmailResult


def test_brand_directory_and_profile_update(client, seed_brand):
    client.post("/api/collabs/", json={
        "brand_id": seed_brand.id,
        "status": "confirmed",
        "campaign_type": "Instagram Reel",
        "budget": 20000,
    })
    directory = client.get("/api/brands/directory")
    assert directory.status_code == 200
    assert directory.json()[0]["collaboration_count"] == 1
    assert directory.json()[0]["active_collaboration_count"] == 1

    updated = client.patch(f"/api/brands/{seed_brand.id}", json={
        "contact_person": "Maya Singh",
        "notes": "Repeat partner",
    })
    assert updated.status_code == 200
    assert updated.json()["contact_person"] == "Maya Singh"

    detail = client.get(f"/api/brands/{seed_brand.id}")
    assert detail.json()["notes"] == "Repeat partner"
    assert len(detail.json()["collabs"]) == 1


def test_invoice_ledger_and_status(client, seed_brand):
    created = client.post("/api/invoices/", json={
        "brand_id": seed_brand.id,
        "line_items": [
            {"description": "Instagram Reel", "quantity": 1, "rate": 20000},
            {"description": "Stories", "quantity": 2, "rate": 2500},
        ],
        "tax_percent": 18,
        "payment_terms": "Due within 15 days",
    })
    assert created.status_code == 200
    invoice = created.json()
    assert invoice["subtotal"] == 25000
    assert invoice["total"] == 29500
    assert invoice["invoice_number"].startswith("INV-")

    sent = client.patch(f"/api/invoices/{invoice['id']}/status?status=sent")
    assert sent.status_code == 200
    ledger = client.get("/api/invoices/ledger").json()
    assert ledger["total_invoiced"] == 29500
    assert ledger["total_outstanding"] == 29500

    paid = client.patch(f"/api/invoices/{invoice['id']}/status?status=paid")
    assert paid.status_code == 200
    ledger = client.get("/api/invoices/ledger").json()
    assert ledger["total_received"] == 29500
    assert ledger["total_outstanding"] == 0


def test_invoice_email_delivery_and_payment_reminder(client, seed_brand, monkeypatch):
    due_date = datetime.now(timezone.utc) - timedelta(days=2)
    invoice = client.post("/api/invoices/", json={
        "brand_id": seed_brand.id,
        "line_items": [{"description": "Campaign package", "quantity": 1, "rate": 12000}],
        "due_date": due_date.isoformat(),
    }).json()
    deliveries = []

    rendered_statuses = []

    def fake_pdf(invoice, brand, **kwargs):
        rendered_statuses.append(kwargs.get("status_override"))
        return b"%PDF-test"

    monkeypatch.setattr(invoice_router, "_render_invoice_pdf", fake_pdf)

    def fake_delivery(payload, pdf_bytes, **kwargs):
        deliveries.append({"payload": payload, "pdf": pdf_bytes, **kwargs})
        return EmailResult(payload["recipient"], True, message_id=f"email-{len(deliveries)}")

    monkeypatch.setattr(invoice_router.email_service, "send_invoice_delivery", fake_delivery)

    sent = client.post(f"/api/invoices/{invoice['id']}/send")
    assert sent.status_code == 200
    assert sent.json()["status"] == "sent"
    assert sent.json()["recipient"] == "maya@notion.com"
    assert deliveries[0]["pdf"] == b"%PDF-test"
    assert "reminder" not in deliveries[0]
    assert rendered_statuses[0] == "sent"

    reminded = client.post(f"/api/invoices/{invoice['id']}/remind")
    assert reminded.status_code == 200
    assert reminded.json()["status"] == "overdue"
    assert reminded.json()["reminder_count"] == 1
    assert deliveries[1]["reminder"] is True
    assert rendered_statuses[1] == "overdue"

    listed = client.get("/api/invoices/").json()[0]
    assert listed["sent_at"] is not None
    assert listed["last_reminded_at"] is not None
    assert listed["email_message_id"] == "email-2"
