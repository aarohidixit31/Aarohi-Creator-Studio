from datetime import datetime, timedelta, timezone

from app import models
from app.routers import invoices as invoice_router
from app.services.email import EmailResult


def test_csv_history_import_reuses_brands_and_skips_duplicates(client, db, seed_brand):
    csv_body = """source_id,brand_name,contact_person,email,phone,campaign_type,status,budget,deadline,deliverables,content_link,created_at,notes,show_on_media_kit,media_kit_summary
notion-2025,Notion,Maya,maya@notion.com,,Instagram Reel,Payment Recieved,"₹25,000",15/06/2025,1 Reel,https://instagram.com/reel/notion,2025-05-01,Successful campaign,yes,Popular productivity partnership
notion-2025,Notion,Maya,maya@notion.com,,Instagram Reel,Payment Received,25000,2025-06-15,1 Reel,https://instagram.com/reel/notion,2025-05-01,Duplicate row,no,
figma-2024,Figma,Ria,ria@figma.com,+91 99999 11111,YouTube Integration,Closed,40000,2024-12-20,1 Video,https://youtube.com/watch?v=figma,2024-11-01,Historical partnership,no,
broken,Invalid Brand,,bad-email,,Reel,Closed,10000,not-a-date,,,,,,
"""
    response = client.post(
        "/api/brands/import-history",
        files={"file": ("history.csv", csv_body.encode("utf-8"), "text/csv")},
    )
    assert response.status_code == 200
    result = response.json()
    assert result["rows_received"] == 4
    assert result["brands_created"] == 1
    assert result["brands_reused"] == 1
    assert result["collabs_created"] == 2
    assert result["duplicates_skipped"] == 1
    assert result["rows_failed"] == 1
    assert result["media_kit_added"] == 1

    notion = db.query(models.Brand).filter_by(email="maya@notion.com").one()
    assert len(notion.collabs) == 1
    assert notion.collabs[0].status == "payment_received"
    assert notion.collabs[0].budget == 25000
    assert notion.collabs[0].details["import_source"] == "history.csv"
    assert db.query(models.Brand).filter_by(email="ria@figma.com").count() == 1
    media_kit = db.query(models.MediaKitContent).one()
    assert media_kit.draft_content["past_collabs"][0]["brand"] == "Notion"

    earnings = client.get("/api/invoices/ledger").json()
    assert earnings["collaboration_count"] == 2
    assert earnings["total_collaboration_value"] == 65000
    assert earnings["historical_received"] == 25000
    assert earnings["total_business_received"] == 25000

    repeated = client.post(
        "/api/brands/import-history",
        files={"file": ("history.csv", csv_body.encode("utf-8"), "text/csv")},
    ).json()
    assert repeated["collabs_created"] == 0
    assert repeated["duplicates_skipped"] == 3


def test_brand_directory_and_profile_update(client, db, seed_brand):
    collaboration = client.post("/api/collabs/", json={
        "brand_id": seed_brand.id,
        "status": "confirmed",
        "campaign_type": "Instagram Reel",
        "budget": 20000,
        "deliverables": "1 Reel + 2 Stories",
    }).json()
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

    added = client.post(f"/api/brands/{seed_brand.id}/collabs/{collaboration['id']}/media-kit")
    assert added.status_code == 200
    assert added.json()["added"] is True
    draft = db.query(models.MediaKitContent).one().draft_content
    assert draft["past_collabs"][0]["summary"] == "1 Reel + 2 Stories"


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


def test_duplicate_invoice_requires_explicit_override(client, seed_brand):
    collab = client.post("/api/collabs/", json={
        "brand_id": seed_brand.id,
        "campaign_type": "Launch Reel",
        "budget": 18000,
    }).json()
    payload = {
        "brand_id": seed_brand.id,
        "collab_id": collab["id"],
        "line_items": [{"description": "Launch Reel", "quantity": 1, "rate": 18000}],
    }
    first = client.post("/api/invoices/", json=payload)
    assert first.status_code == 200

    blocked = client.post("/api/invoices/", json=payload)
    assert blocked.status_code == 409
    assert blocked.json()["detail"]["code"] == "invoice_exists"
    assert blocked.json()["detail"]["invoice_number"] == first.json()["invoice_number"]

    allowed = client.post("/api/invoices/", json={**payload, "allow_duplicate": True})
    assert allowed.status_code == 200
    assert allowed.json()["id"] != first.json()["id"]


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
