import html
import json
import logging
import os
import base64
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .. import models
from ..database import SessionLocal

logger = logging.getLogger(__name__)

RESEND_ENDPOINT = "https://api.resend.com/emails"


@dataclass
class EmailResult:
    recipient: str
    sent: bool
    message_id: str | None = None
    error: str | None = None
    disabled: bool = False


def email_is_configured() -> bool:
    return bool(os.getenv("RESEND_API_KEY") and os.getenv("EMAIL_FROM"))


def _safe(value: Any, fallback: str = "Not provided") -> str:
    if value in (None, ""):
        return fallback
    return html.escape(str(value))


def _format_budget(value: float | None) -> str:
    if value is None:
        return "Not specified"
    return f"INR {value:,.0f}"


def _email_shell(preheader: str, body: str) -> str:
    return f"""<!doctype html>
<html>
<body style="margin:0;background:#f3f5fb;color:#14161a;font-family:Arial,sans-serif;">
  <div style="display:none;max-height:0;overflow:hidden;opacity:0;">{_safe(preheader)}</div>
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background:#f3f5fb;padding:28px 12px;">
    <tr><td align="center">
      <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="max-width:620px;background:#ffffff;border:1px solid #e2e6f0;border-radius:16px;overflow:hidden;">
        <tr><td style="height:8px;background:linear-gradient(90deg,#111b45 0%,#5b5fef 78%,#f5d929 78%);"></td></tr>
        <tr><td style="padding:30px 34px 12px;">
          <table role="presentation" width="100%"><tr>
            <td>
              <span style="display:inline-block;background:#111b45;color:#f5d929;border-radius:9px;padding:10px 9px;font-weight:800;">AI</span>
              <strong style="margin-left:10px;color:#111b45;font-size:17px;">Aarohi Inframe</strong>
            </td>
            <td align="right" style="color:#7a8298;font-size:11px;">CREATOR STUDIO</td>
          </tr></table>
        </td></tr>
        <tr><td style="padding:18px 34px 34px;">{body}</td></tr>
        <tr><td style="padding:18px 34px;background:#111b45;color:#aeb8dd;font-size:11px;">
          Tech content, thoughtfully created.
        </td></tr>
      </table>
    </td></tr>
  </table>
</body>
</html>"""


def _manager_email(inquiry: dict, collab_id: int) -> tuple[str, str]:
    frontend_url = os.getenv("FRONTEND_URL", "http://localhost:5173").rstrip("/")
    workspace_url = f"{frontend_url}/admin/collabs/{collab_id}"
    subject = f"New collaboration inquiry - {inquiry['brand_name']}"
    body = f"""
      <p style="margin:0 0 7px;color:#5b5fef;font-size:11px;font-weight:700;letter-spacing:.1em;text-transform:uppercase;">New inquiry</p>
      <h1 style="margin:0 0 12px;color:#111b45;font-size:27px;line-height:1.2;">{_safe(inquiry['brand_name'])} wants to collaborate</h1>
      <p style="margin:0 0 24px;color:#616a80;font-size:14px;line-height:1.6;">A new lead has been added to your collaboration pipeline.</p>
      <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background:#f6f7ff;border-left:4px solid #5b5fef;border-radius:8px;">
        <tr><td style="padding:18px 20px;color:#737c92;font-size:12px;">CONTACT</td><td style="padding:18px 20px;color:#111b45;font-size:13px;font-weight:700;">{_safe(inquiry['contact_person'])}<br><span style="font-weight:400;color:#596177;">{_safe(inquiry['email'])}</span></td></tr>
        <tr><td style="padding:0 20px 18px;color:#737c92;font-size:12px;">CAMPAIGN</td><td style="padding:0 20px 18px;color:#111b45;font-size:13px;font-weight:700;">{_safe(inquiry.get('campaign_type'))}</td></tr>
        <tr><td style="padding:0 20px 18px;color:#737c92;font-size:12px;">BUDGET</td><td style="padding:0 20px 18px;color:#111b45;font-size:13px;font-weight:700;">{_format_budget(inquiry.get('budget'))}</td></tr>
        <tr><td style="padding:0 20px 18px;color:#737c92;font-size:12px;">DELIVERABLES</td><td style="padding:0 20px 18px;color:#111b45;font-size:13px;">{_safe(inquiry.get('deliverables'))}</td></tr>
      </table>
      <div style="margin-top:24px;">
        <a href="{html.escape(workspace_url)}" style="display:inline-block;background:#2949d3;color:#ffffff;border-radius:9px;padding:13px 20px;text-decoration:none;font-size:13px;font-weight:700;">Open collaboration workspace</a>
      </div>
      <p style="margin:24px 0 0;color:#7a8298;font-size:12px;line-height:1.6;"><strong>Brief:</strong> {_safe(inquiry.get('brief'))}</p>
    """
    return subject, _email_shell("A new brand collaboration inquiry has arrived.", body)


def _brand_email(inquiry: dict) -> tuple[str, str]:
    first_name = _safe(inquiry["contact_person"]).split()[0]
    subject = "We received your collaboration request"
    body = f"""
      <p style="margin:0 0 7px;color:#5b5fef;font-size:11px;font-weight:700;letter-spacing:.1em;text-transform:uppercase;">Request received</p>
      <h1 style="margin:0 0 14px;color:#111b45;font-size:27px;line-height:1.2;">Thanks for reaching out, {first_name}!</h1>
      <p style="margin:0 0 18px;color:#596177;font-size:14px;line-height:1.7;">Your collaboration request for <strong>{_safe(inquiry['brand_name'])}</strong> is safely in our pipeline. Aarohi or her manager will review the brief and respond within <strong>24-48 hours</strong>.</p>
      <div style="margin:22px 0;padding:18px 20px;background:#fff8cf;border-radius:9px;color:#534c1c;font-size:13px;line-height:1.7;">
        <strong style="color:#111b45;">What happens next?</strong><br>
        We review the campaign fit, deliverables, timeline, and budget, then reply to this email with availability and next steps.
      </div>
      <p style="margin:0;color:#596177;font-size:14px;line-height:1.7;">Looking forward to learning more about the campaign.</p>
      <p style="margin:22px 0 0;color:#111b45;font-size:14px;"><strong>Aarohi Dixit</strong><br><span style="color:#7a8298;">Tech Content Creator</span></p>
    """
    return subject, _email_shell("Your collaboration request has been received.", body)


def _send_email(
    recipient: str,
    subject: str,
    email_html: str,
    idempotency_key: str,
    attachments: list[dict] | None = None,
) -> EmailResult:
    api_key = os.getenv("RESEND_API_KEY")
    sender = os.getenv("EMAIL_FROM")
    if not api_key or not sender:
        return EmailResult(
            recipient=recipient,
            sent=False,
            disabled=True,
            error="RESEND_API_KEY or EMAIL_FROM is not configured",
        )

    payload = {
        "from": sender,
        "to": [recipient],
        "subject": subject,
        "html": email_html,
    }
    reply_to = os.getenv("REPLY_TO_EMAIL") or os.getenv("ADMIN_EMAIL")
    if reply_to:
        payload["reply_to"] = reply_to
    if attachments:
        payload["attachments"] = attachments

    request = Request(
        RESEND_ENDPOINT,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Idempotency-Key": idempotency_key,
            "User-Agent": "aarohi-creator-dashboard/1.0",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=10) as response:
            result = json.loads(response.read().decode("utf-8"))
        return EmailResult(recipient=recipient, sent=True, message_id=result.get("id"))
    except HTTPError as exc:
        response_body = exc.read().decode("utf-8", errors="replace")
        logger.error("Resend rejected email to %s: %s", recipient, response_body)
        return EmailResult(recipient=recipient, sent=False, error=f"Resend HTTP {exc.code}")
    except (URLError, TimeoutError, OSError, ValueError) as exc:
        logger.error("Could not send email to %s: %s", recipient, exc)
        return EmailResult(recipient=recipient, sent=False, error=str(exc))


def _record_delivery(collab_id: int, manager: EmailResult, brand: EmailResult) -> None:
    db = SessionLocal()
    try:
        collab = db.query(models.Collab).filter(models.Collab.id == collab_id).first()
        if not collab:
            return
        details = dict(collab.details or {})
        activity_log = list(details.get("activity_log") or [])
        now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

        if manager.disabled and brand.disabled:
            summary = "Email notifications skipped - Resend is not configured"
            action = "email_disabled"
        else:
            sent_to = []
            failed_for = []
            if manager.sent:
                sent_to.append("manager")
            else:
                failed_for.append("manager")
            if brand.sent:
                sent_to.append("brand")
            else:
                failed_for.append("brand")
            summary = f"Email sent to {', '.join(sent_to)}" if sent_to else "Email delivery failed"
            if failed_for:
                summary += f"; failed for {', '.join(failed_for)}"
            action = "email_delivery"

        activity_log.append({
            "timestamp": now,
            "action": action,
            "detail": summary,
            "from_status": None,
            "to_status": None,
        })
        details["notification_delivery"] = {
            "manager": {
                "sent": manager.sent,
                "message_id": manager.message_id,
                "error": manager.error,
            },
            "brand": {
                "sent": brand.sent,
                "message_id": brand.message_id,
                "error": brand.error,
            },
            "updated_at": now,
        }
        details["activity_log"] = activity_log[-100:]
        collab.details = details
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("Could not record email delivery for collaboration %s", collab_id)
    finally:
        db.close()


def send_inquiry_notifications(collab_id: int, inquiry: dict) -> None:
    manager_subject, manager_html = _manager_email(inquiry, collab_id)
    brand_subject, brand_html = _brand_email(inquiry)
    internal_recipients = list(dict.fromkeys(
        recipient
        for recipient in (
            os.getenv("ADMIN_EMAIL"),
            os.getenv("ADMIN_NOTIFICATION_EMAIL"),
        )
        if recipient
    ))
    internal_results = [
        _send_email(
            recipient,
            manager_subject,
            manager_html,
            f"collab-{collab_id}-internal-{index}-v1",
        )
        for index, recipient in enumerate(internal_recipients, start=1)
    ]
    if internal_results:
        failed = [result for result in internal_results if not result.sent]
        manager = EmailResult(
            recipient=", ".join(result.recipient for result in internal_results),
            sent=not failed,
            message_id=", ".join(
                result.message_id for result in internal_results if result.message_id
            ) or None,
            error="; ".join(
                f"{result.recipient}: {result.error}" for result in failed
            ) or None,
            disabled=all(result.disabled for result in internal_results),
        )
    else:
        manager = EmailResult(
            "",
            False,
            error="Aarohi/manager recipients are not configured",
            disabled=True,
        )
    brand = _send_email(
        inquiry["email"],
        brand_subject,
        brand_html,
        f"collab-{collab_id}-brand-v1",
    )
    _record_delivery(collab_id, manager, brand)


def _invoice_attachment(invoice_number: str, pdf_bytes: bytes) -> list[dict]:
    return [{
        "filename": f"{invoice_number}.pdf",
        "content": base64.b64encode(pdf_bytes).decode("ascii"),
    }]


def _invoice_delivery_email(invoice: dict, reminder: bool = False) -> tuple[str, str]:
    contact_name = _safe(invoice.get("contact_person"), "there").split()[0]
    amount = f"INR {float(invoice['total']):,.0f}"
    due_date = _safe(invoice.get("due_date"), "As per agreed payment terms")
    if reminder:
        subject = f"Payment reminder: {invoice['invoice_number']}"
        heading = f"A quick payment reminder for {invoice['invoice_number']}"
        intro = (
            f"Hi {contact_name}, this is a friendly reminder that payment of "
            f"<strong>{amount}</strong> for <strong>{_safe(invoice['invoice_number'])}</strong> "
            f"is still pending."
        )
        preheader = f"Payment reminder for {invoice['invoice_number']}."
        note = "If payment has already been processed, please reply with the transaction reference and disregard this reminder."
    else:
        subject = f"Invoice {invoice['invoice_number']} from Aarohi Inframe"
        heading = f"Invoice {invoice['invoice_number']}"
        intro = (
            f"Hi {contact_name}, thank you for collaborating with Aarohi Inframe. "
            f"Please find the invoice for <strong>{amount}</strong> attached as a PDF."
        )
        preheader = f"Your invoice {invoice['invoice_number']} is attached."
        note = "Please reply to this email if your finance team needs any additional information."

    body = f"""
      <p style="margin:0 0 7px;color:#5b5fef;font-size:11px;font-weight:700;letter-spacing:.1em;text-transform:uppercase;">{'Payment follow-up' if reminder else 'Invoice attached'}</p>
      <h1 style="margin:0 0 14px;color:#111b45;font-size:27px;line-height:1.2;">{heading}</h1>
      <p style="margin:0 0 20px;color:#596177;font-size:14px;line-height:1.7;">{intro}</p>
      <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background:#f6f7ff;border-left:4px solid #5b5fef;border-radius:8px;">
        <tr><td style="padding:17px 20px;color:#737c92;font-size:11px;">INVOICE</td><td align="right" style="padding:17px 20px;color:#111b45;font-size:13px;font-weight:700;">{_safe(invoice['invoice_number'])}</td></tr>
        <tr><td style="padding:0 20px 17px;color:#737c92;font-size:11px;">AMOUNT</td><td align="right" style="padding:0 20px 17px;color:#111b45;font-size:16px;font-weight:800;">{amount}</td></tr>
        <tr><td style="padding:0 20px 17px;color:#737c92;font-size:11px;">DUE DATE</td><td align="right" style="padding:0 20px 17px;color:#111b45;font-size:13px;font-weight:700;">{due_date}</td></tr>
      </table>
      <div style="margin:22px 0;padding:16px 18px;background:#fff8cf;border-radius:9px;color:#534c1c;font-size:12px;line-height:1.7;">
        <strong>Payment terms:</strong> {_safe(invoice.get('payment_terms'))}
      </div>
      <p style="margin:0;color:#7a8298;font-size:12px;line-height:1.7;">{note}</p>
      <p style="margin:22px 0 0;color:#111b45;font-size:14px;"><strong>Aarohi Dixit</strong><br><span style="color:#7a8298;">Tech Content Creator · Aarohi Inframe</span></p>
    """
    return subject, _email_shell(preheader, body)


def send_invoice_delivery(
    invoice: dict,
    pdf_bytes: bytes,
    *,
    reminder: bool = False,
    idempotency_key: str,
) -> EmailResult:
    subject, email_html = _invoice_delivery_email(invoice, reminder=reminder)
    return _send_email(
        invoice["recipient"],
        subject,
        email_html,
        idempotency_key,
        attachments=_invoice_attachment(invoice["invoice_number"], pdf_bytes),
    )


def send_manager_attention_digest(items: list[dict], idempotency_key: str) -> EmailResult:
    recipient = os.getenv("ADMIN_NOTIFICATION_EMAIL") or os.getenv("ADMIN_EMAIL")
    if not recipient:
        return EmailResult("", False, disabled=True, error="Manager recipient is not configured")

    frontend_url = os.getenv("FRONTEND_URL", "http://localhost:5173").rstrip("/")
    rows = "".join(
        f"""
        <tr>
          <td style="padding:13px 14px;border-top:1px solid #e8ebf2;color:#111b45;font-size:12px;font-weight:700;">{_safe(item['brand_name'])}</td>
          <td style="padding:13px 14px;border-top:1px solid #e8ebf2;color:#596177;font-size:12px;">{_safe(item['reason'])}</td>
          <td style="padding:13px 14px;border-top:1px solid #e8ebf2;color:#5b5fef;font-size:11px;font-weight:700;">{_safe(item['age'])}</td>
        </tr>
        """
        for item in items
    )
    body = f"""
      <p style="margin:0 0 7px;color:#5b5fef;font-size:11px;font-weight:700;letter-spacing:.1em;text-transform:uppercase;">Daily manager digest</p>
      <h1 style="margin:0 0 12px;color:#111b45;font-size:27px;line-height:1.2;">{len(items)} collaboration follow-up{'s' if len(items) != 1 else ''} need attention</h1>
      <p style="margin:0 0 22px;color:#596177;font-size:14px;line-height:1.7;">These inquiries or scheduled follow-ups are waiting for action.</p>
      <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="border:1px solid #e2e6f0;border-radius:9px;border-collapse:separate;overflow:hidden;">
        <tr style="background:#f6f7ff;"><th align="left" style="padding:11px 14px;color:#737c92;font-size:10px;">BRAND</th><th align="left" style="padding:11px 14px;color:#737c92;font-size:10px;">ACTION</th><th align="left" style="padding:11px 14px;color:#737c92;font-size:10px;">WAITING</th></tr>
        {rows}
      </table>
      <div style="margin-top:24px;">
        <a href="{html.escape(frontend_url)}/admin/attention" style="display:inline-block;background:#2949d3;color:#ffffff;border-radius:9px;padding:13px 20px;text-decoration:none;font-size:13px;font-weight:700;">Open manager attention queue</a>
      </div>
    """
    return _send_email(
        recipient,
        f"Daily follow-up digest: {len(items)} items need attention",
        _email_shell("Your creator dashboard has follow-ups waiting.", body),
        idempotency_key,
    )
