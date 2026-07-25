import os
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session, joinedload

from .. import models
from ..auth import get_current_admin
from ..database import get_db
from ..services import email as email_service
from .invoices import _email_payload, _render_invoice_pdf

router = APIRouter(prefix="/api/automation", tags=["automation"])


def _utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _run_daily(db: Session) -> dict:
    now = datetime.now(timezone.utc)
    interval_days = max(1, int(os.getenv("INVOICE_REMINDER_INTERVAL_DAYS", "3")))
    reminder_cutoff = now - timedelta(days=interval_days)
    invoice_sent = 0
    invoice_skipped = 0
    errors = []

    invoices = (
        db.query(models.Invoice)
        .options(joinedload(models.Invoice.brand))
        .filter(models.Invoice.status.in_(("sent", "overdue")))
        .all()
    )
    for invoice in invoices:
        due_at = _utc(invoice.due_date)
        reminded_at = _utc(invoice.last_reminded_at)
        if not due_at or due_at >= now or (reminded_at and reminded_at > reminder_cutoff):
            invoice_skipped += 1
            continue
        if not invoice.brand or not invoice.brand.email:
            errors.append(f"{invoice.invoice_number}: brand billing email is missing")
            continue

        reminder_number = (invoice.reminder_count or 0) + 1
        try:
            result = email_service.send_invoice_delivery(
                _email_payload(invoice, invoice.brand),
                _render_invoice_pdf(invoice, invoice.brand, status_override="overdue"),
                reminder=True,
                idempotency_key=f"invoice-{invoice.id}-auto-reminder-{reminder_number}",
            )
        except Exception as exc:
            errors.append(f"{invoice.invoice_number}: {exc}")
            continue
        if not result.sent:
            errors.append(f"{invoice.invoice_number}: {result.error or 'delivery failed'}")
            continue

        invoice.status = "overdue"
        invoice.last_reminded_at = now.replace(tzinfo=None)
        invoice.reminder_count = reminder_number
        invoice.email_message_id = result.message_id
        invoice_sent += 1

    attention_items = []
    collabs = (
        db.query(models.Collab)
        .options(joinedload(models.Collab.brand))
        .filter(models.Collab.status.in_(("new_inquiry", "in_discussion", "negotiating")))
        .all()
    )
    for collab in collabs:
        created_at = _utc(collab.created_at) or now
        follow_up_raw = (collab.details or {}).get("follow_up_at")
        try:
            follow_up_at = (
                datetime.fromisoformat(follow_up_raw.replace("Z", "+00:00"))
                if isinstance(follow_up_raw, str)
                else _utc(follow_up_raw)
            )
        except ValueError:
            follow_up_at = None
        if follow_up_at and follow_up_at.tzinfo is None:
            follow_up_at = follow_up_at.replace(tzinfo=timezone.utc)

        if follow_up_at and follow_up_at <= now:
            reason = "Scheduled follow-up is due"
            waiting_since = follow_up_at
        elif collab.status == "new_inquiry" and created_at <= now - timedelta(hours=24):
            reason = "New inquiry has not moved forward"
            waiting_since = created_at
        else:
            continue
        waiting_days = max(1, (now - waiting_since).days)
        attention_items.append({
            "brand_name": collab.brand.name if collab.brand else f"Brand #{collab.brand_id}",
            "reason": reason,
            "age": f"{waiting_days} day{'s' if waiting_days != 1 else ''}",
        })

    digest_sent = False
    if attention_items:
        digest = email_service.send_manager_attention_digest(
            attention_items,
            idempotency_key=f"manager-digest-{now.date().isoformat()}",
        )
        digest_sent = digest.sent
        if not digest.sent:
            errors.append(f"Manager digest: {digest.error or 'delivery failed'}")

    db.commit()
    return {
        "ran_at": now.isoformat(),
        "invoice_reminders_sent": invoice_sent,
        "invoice_reminders_skipped": invoice_skipped,
        "collaboration_follow_ups": len(attention_items),
        "manager_digest_sent": digest_sent,
        "errors": errors,
    }


def _ensure_enabled() -> None:
    if os.getenv("AUTOMATION_ENABLED", "").casefold() not in ("1", "true", "yes"):
        raise HTTPException(503, "Daily automation is disabled. Set AUTOMATION_ENABLED=true.")


@router.get("/status")
def automation_status(admin=Depends(get_current_admin)):
    return {
        "enabled": os.getenv("AUTOMATION_ENABLED", "").casefold() in ("1", "true", "yes"),
        "email_configured": email_service.email_is_configured(),
        "reminder_interval_days": max(1, int(os.getenv("INVOICE_REMINDER_INTERVAL_DAYS", "3"))),
        "cron_secret_configured": bool(os.getenv("CRON_SECRET")),
    }


@router.post("/run")
def run_daily_manually(
    db: Session = Depends(get_db),
    admin=Depends(get_current_admin),
):
    _ensure_enabled()
    return _run_daily(db)


@router.post("/cron")
def run_daily_from_cron(
    db: Session = Depends(get_db),
    x_cron_secret: str | None = Header(default=None),
):
    _ensure_enabled()
    expected = os.getenv("CRON_SECRET")
    if not expected or not x_cron_secret or not secrets.compare_digest(expected, x_cron_secret):
        raise HTTPException(401, "Invalid cron secret")
    return _run_daily(db)
