from app.services import email
from app.services.email import EmailResult


def test_inquiry_alerts_go_to_aarohi_manager_and_brand(monkeypatch):
    monkeypatch.setenv("ADMIN_EMAIL", "aarohi@example.com")
    monkeypatch.setenv("ADMIN_NOTIFICATION_EMAIL", "manager@example.com")
    recipients = []
    recorded = []

    def fake_send(recipient, subject, email_html, idempotency_key, attachments=None):
        recipients.append(recipient)
        return EmailResult(recipient, True, message_id=f"id-{len(recipients)}")

    monkeypatch.setattr(email, "_send_email", fake_send)
    monkeypatch.setattr(
        email,
        "_record_delivery",
        lambda collab_id, manager, brand: recorded.append((collab_id, manager, brand)),
    )

    email.send_inquiry_notifications(42, {
        "brand_name": "Notion",
        "contact_person": "Maya Singh",
        "email": "maya@notion.com",
        "campaign_type": "Instagram Reel",
        "budget": 20000,
        "deliverables": "One Reel",
        "brief": "Launch campaign",
    })

    assert recipients == [
        "aarohi@example.com",
        "manager@example.com",
        "maya@notion.com",
    ]
    assert recorded[0][1].sent is True
    assert recorded[0][1].recipient == "aarohi@example.com, manager@example.com"
