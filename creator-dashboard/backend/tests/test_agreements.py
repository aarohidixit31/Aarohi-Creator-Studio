from app import models
from app.routers import agreements
from app.services.email import EmailResult
from app.services.storage import StorageResult


def create_collaboration(client, brand_id: int) -> int:
    response = client.post("/api/collabs/", json={
        "brand_id": brand_id,
        "campaign_type": "Instagram Reel",
        "deliverables": "1 Reel and 2 Stories",
        "budget": 45000,
    })
    assert response.status_code == 201
    return response.json()["id"]


def agreement_payload():
    return {
        "effective_date": "2026-08-15T12:00:00Z",
        "termination_date": "2026-09-15T12:00:00Z",
        "deliverables": "1 Instagram Reel and 2 Stories",
        "timeline": "Draft within 7 working days of product receipt",
        "total_amount": 45000,
        "payment_structure": "50% advance, 50% after publication",
        "payment_due_days": 5,
        "revision_limit": 2,
        "content_live_months": 6,
        "usage_rights": "Organic reposting with creator credit for 90 days.",
        "additional_terms": "Product delivery is the Brand's responsibility.",
    }


def test_agreement_defaults_and_draft_are_stored_in_collaboration(client, db, seed_brand):
    collab_id = create_collaboration(client, seed_brand.id)

    initial = client.get(f"/api/agreements/{collab_id}")
    assert initial.status_code == 200
    assert initial.json()["status"] == "not_created"
    assert initial.json()["agreement_number"].startswith("AGR-")
    assert initial.json()["total_amount"] == 45000

    saved = client.put(f"/api/agreements/{collab_id}", json=agreement_payload())
    assert saved.status_code == 200
    assert saved.json()["status"] == "draft"
    assert saved.json()["revision_limit"] == 2

    db.expire_all()
    collab = db.query(models.Collab).filter(models.Collab.id == collab_id).one()
    assert collab.details["agreement"]["total_amount"] == 45000
    assert any(item["action"] == "agreement_updated" for item in collab.details["activity_log"])


def test_agreement_pdf_and_email_delivery_update_workflow(client, db, seed_brand, monkeypatch):
    collab_id = create_collaboration(client, seed_brand.id)
    unsaved = client.post(f"/api/agreements/{collab_id}/send")
    assert unsaved.status_code == 400
    assert unsaved.json()["detail"] == "Save the agreement draft before sending it"
    client.put(f"/api/agreements/{collab_id}", json=agreement_payload())
    monkeypatch.setattr(agreements, "_render_pdf", lambda *args: b"%PDF-test")
    sent = {}

    def fake_delivery(**kwargs):
        sent.update(kwargs)
        return EmailResult(kwargs["recipient"], True, message_id="email_agreement_123")

    monkeypatch.setattr(agreements.email_service, "send_agreement_delivery", fake_delivery)

    pdf = client.get(f"/api/agreements/{collab_id}/pdf")
    assert pdf.status_code == 200
    assert pdf.headers["content-type"] == "application/pdf"
    assert pdf.content == b"%PDF-test"

    delivered = client.post(f"/api/agreements/{collab_id}/send")
    assert delivered.status_code == 200
    assert delivered.json()["agreement"]["status"] == "sent"
    assert delivered.json()["agreement"]["email_message_id"] == "email_agreement_123"
    assert sent["recipient"] == seed_brand.email
    assert sent["pdf_bytes"] == b"%PDF-test"

    db.expire_all()
    collab = db.query(models.Collab).filter(models.Collab.id == collab_id).one()
    assert any(item["action"] == "agreement_sent" for item in collab.details["activity_log"])


def test_signed_agreement_upload_is_validated_and_stored(client, seed_brand, monkeypatch):
    collab_id = create_collaboration(client, seed_brand.id)
    monkeypatch.setattr(
        agreements,
        "store_document",
        lambda *args, **kwargs: StorageResult(
            url="https://res.cloudinary.com/example/raw/upload/signed.pdf",
            backend="cloudinary",
            public_id="aarohi-inframe/agreements/signed",
        ),
    )

    rejected = client.post(
        f"/api/agreements/{collab_id}/signed",
        files={"file": ("signed.txt", b"not a signature", "text/plain")},
    )
    assert rejected.status_code == 400

    uploaded = client.post(
        f"/api/agreements/{collab_id}/signed",
        files={"file": ("signed.pdf", b"%PDF-signed", "application/pdf")},
    )
    assert uploaded.status_code == 200
    assert uploaded.json()["status"] == "signed"
    assert uploaded.json()["signed_file_url"].endswith("signed.pdf")
    assert uploaded.json()["signed_at"] is not None


def test_agreement_rejects_negative_commercial_terms(client, seed_brand):
    collab_id = create_collaboration(client, seed_brand.id)
    payload = agreement_payload()
    payload["revision_limit"] = -1
    response = client.put(f"/api/agreements/{collab_id}", json=payload)
    assert response.status_code == 400
    assert response.json()["detail"] == "Agreement numeric terms cannot be negative"

    payload = agreement_payload()
    payload["total_amount"] = -100
    response = client.put(f"/api/agreements/{collab_id}", json=payload)
    assert response.status_code == 400
