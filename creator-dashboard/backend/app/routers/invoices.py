import os
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session, joinedload
from jinja2 import Environment, FileSystemLoader
from .. import models, schemas
from ..database import get_db
from ..auth import get_current_admin
from ..services import email as email_service

router = APIRouter(prefix="/api/invoices", tags=["invoices"])

TEMPLATE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates")
jinja_env = Environment(loader=FileSystemLoader(TEMPLATE_DIR))

# --- Edit these to match your details, or move into MediaKitContent later ---
CREATOR_NAME = os.getenv("CREATOR_NAME", "Aarohi Dixit")
CREATOR_TAGLINE = os.getenv("CREATOR_TAGLINE", "Tech Content Creator")
CREATOR_EMAIL = os.getenv("CREATOR_EMAIL", os.getenv("ADMIN_EMAIL", "aarohi.inframe@gmail.com"))
PAYMENT_DETAILS = os.getenv("PAYMENT_DETAILS", "UPI: yourupi@bank | Bank transfer details on request")


def _generate_invoice_number(db: Session) -> str:
    year = datetime.now(timezone.utc).year
    count_this_year = (
        db.query(models.Invoice)
        .filter(models.Invoice.invoice_number.like(f"INV-{year}-%"))
        .count()
    )
    return f"INV-{year}-{count_this_year + 1:03d}"


def _render_invoice_pdf(
    invoice: models.Invoice,
    brand: models.Brand,
    *,
    status_override: str | None = None,
) -> bytes:
    # WeasyPrint depends on native rendering libraries. Import it only when a
    # PDF is requested or attached to an email.
    from weasyprint import HTML

    template = jinja_env.get_template("invoice.html")
    html_content = template.render(
        creator_name=CREATOR_NAME,
        creator_tagline=CREATOR_TAGLINE,
        creator_email=CREATOR_EMAIL,
        invoice_number=invoice.invoice_number,
        invoice_status=status_override or invoice.status,
        invoice_date=invoice.created_at.strftime("%d %b %Y"),
        due_date=invoice.due_date.strftime("%d %b %Y") if invoice.due_date else None,
        brand_name=brand.name,
        contact_person=brand.contact_person,
        brand_email=brand.email,
        brand_phone=brand.phone,
        line_items=invoice.line_items,
        subtotal=invoice.subtotal,
        tax_percent=invoice.tax_percent,
        total=invoice.total,
        payment_terms=invoice.payment_terms,
        payment_details=PAYMENT_DETAILS,
    )
    return HTML(string=html_content).write_pdf()


def _invoice_and_brand(db: Session, invoice_id: int) -> tuple[models.Invoice, models.Brand]:
    invoice = (
        db.query(models.Invoice)
        .options(joinedload(models.Invoice.brand))
        .filter(models.Invoice.id == invoice_id)
        .first()
    )
    if not invoice:
        raise HTTPException(404, "Invoice not found")
    if not invoice.brand:
        raise HTTPException(409, "This invoice is not connected to a brand")
    return invoice, invoice.brand


def _email_payload(invoice: models.Invoice, brand: models.Brand) -> dict:
    return {
        "recipient": brand.email,
        "contact_person": brand.contact_person,
        "brand_name": brand.name,
        "invoice_number": invoice.invoice_number,
        "total": invoice.total or 0,
        "due_date": invoice.due_date.strftime("%d %b %Y") if invoice.due_date else None,
        "payment_terms": invoice.payment_terms,
    }


@router.post("/", response_model=schemas.InvoiceOut)
def create_invoice(
    payload: schemas.InvoiceCreate,
    db: Session = Depends(get_db),
    admin=Depends(get_current_admin),
):
    brand = db.query(models.Brand).filter(models.Brand.id == payload.brand_id).first()
    if not brand:
        raise HTTPException(404, "Brand not found")

    subtotal = sum(item.quantity * item.rate for item in payload.line_items)
    total = subtotal * (1 + payload.tax_percent / 100)

    invoice = models.Invoice(
        invoice_number=_generate_invoice_number(db),
        brand_id=payload.brand_id,
        collab_id=payload.collab_id,
        line_items=[item.model_dump() for item in payload.line_items],
        subtotal=subtotal,
        tax_percent=payload.tax_percent,
        total=total,
        payment_terms=payload.payment_terms,
        due_date=payload.due_date,
        status="draft",
    )
    db.add(invoice)
    db.commit()
    db.refresh(invoice)
    return invoice


@router.get("/", response_model=list[schemas.InvoiceListOut])
def list_invoices(db: Session = Depends(get_db), admin=Depends(get_current_admin)):
    return (
        db.query(models.Invoice)
        .options(joinedload(models.Invoice.brand))
        .order_by(models.Invoice.created_at.desc())
        .all()
    )


@router.get("/ledger", response_model=schemas.InvoiceLedgerOut)
def invoice_ledger(db: Session = Depends(get_db), admin=Depends(get_current_admin)):
    invoices = db.query(models.Invoice).all()
    paid = [invoice for invoice in invoices if invoice.status == "paid"]
    outstanding = [invoice for invoice in invoices if invoice.status in ("sent", "overdue")]
    drafts = [invoice for invoice in invoices if invoice.status == "draft"]
    return {
        "total_invoiced": sum(invoice.total or 0 for invoice in invoices),
        "total_received": sum(invoice.total or 0 for invoice in paid),
        "total_outstanding": sum(invoice.total or 0 for invoice in outstanding),
        "total_draft": sum(invoice.total or 0 for invoice in drafts),
        "invoice_count": len(invoices),
        "paid_count": len(paid),
        "outstanding_count": len(outstanding),
    }


@router.get("/{invoice_id}/pdf")
def get_invoice_pdf(invoice_id: int, db: Session = Depends(get_db), admin=Depends(get_current_admin)):
    invoice, brand = _invoice_and_brand(db, invoice_id)
    pdf_bytes = _render_invoice_pdf(invoice, brand)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{invoice.invoice_number}.pdf"'},
    )


@router.post("/{invoice_id}/send", response_model=schemas.InvoiceDeliveryOut)
def send_invoice(
    invoice_id: int,
    db: Session = Depends(get_db),
    admin=Depends(get_current_admin),
):
    invoice, brand = _invoice_and_brand(db, invoice_id)
    if not brand.email:
        raise HTTPException(400, "Add a billing email to the brand profile before sending")
    if invoice.status == "paid":
        raise HTTPException(409, "This invoice is already marked as paid")

    result = email_service.send_invoice_delivery(
        _email_payload(invoice, brand),
        _render_invoice_pdf(
            invoice,
            brand,
            status_override=invoice.status if invoice.status in ("sent", "overdue") else "sent",
        ),
        idempotency_key=f"invoice-{invoice.id}-send-{int(datetime.now(timezone.utc).timestamp())}",
    )
    if not result.sent:
        status_code = 503 if result.disabled else 502
        raise HTTPException(status_code, result.error or "Invoice email could not be delivered")

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    invoice.status = "sent"
    invoice.sent_at = now
    invoice.email_message_id = result.message_id
    db.commit()
    return {
        "message": f"Invoice emailed to {brand.email}",
        "status": invoice.status,
        "recipient": brand.email,
        "message_id": result.message_id,
        "sent_at": now,
        "last_reminded_at": invoice.last_reminded_at,
        "reminder_count": invoice.reminder_count or 0,
    }


@router.post("/{invoice_id}/remind", response_model=schemas.InvoiceDeliveryOut)
def remind_invoice(
    invoice_id: int,
    db: Session = Depends(get_db),
    admin=Depends(get_current_admin),
):
    invoice, brand = _invoice_and_brand(db, invoice_id)
    if not brand.email:
        raise HTTPException(400, "Add a billing email to the brand profile before sending a reminder")
    if invoice.status == "draft":
        raise HTTPException(409, "Send the invoice before sending a payment reminder")
    if invoice.status == "paid":
        raise HTTPException(409, "A paid invoice does not need a reminder")

    reminder_number = (invoice.reminder_count or 0) + 1
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    reminder_status = (
        "overdue"
        if invoice.due_date and invoice.due_date.replace(tzinfo=None) < now
        else invoice.status
    )
    result = email_service.send_invoice_delivery(
        _email_payload(invoice, brand),
        _render_invoice_pdf(invoice, brand, status_override=reminder_status),
        reminder=True,
        idempotency_key=f"invoice-{invoice.id}-reminder-{reminder_number}",
    )
    if not result.sent:
        status_code = 503 if result.disabled else 502
        raise HTTPException(status_code, result.error or "Payment reminder could not be delivered")

    invoice.last_reminded_at = now
    invoice.reminder_count = reminder_number
    invoice.email_message_id = result.message_id
    invoice.status = reminder_status
    db.commit()
    return {
        "message": f"Payment reminder emailed to {brand.email}",
        "status": invoice.status,
        "recipient": brand.email,
        "message_id": result.message_id,
        "sent_at": invoice.sent_at,
        "last_reminded_at": now,
        "reminder_count": reminder_number,
    }


@router.patch("/{invoice_id}/status")
def update_invoice_status(
    invoice_id: int,
    status: str,
    db: Session = Depends(get_db),
    admin=Depends(get_current_admin),
):
    if status not in ("draft", "sent", "paid", "overdue"):
        raise HTTPException(400, "Invalid status")
    invoice = db.query(models.Invoice).filter(models.Invoice.id == invoice_id).first()
    if not invoice:
        raise HTTPException(404, "Invoice not found")
    if status == "paid":
        # Database timestamps are stored as naive UTC for compatibility with
        # both SQLite locally and the existing production schema.
        invoice.paid_at = datetime.now(timezone.utc).replace(tzinfo=None)
    else:
        invoice.paid_at = None
    invoice.status = status
    db.commit()
    db.refresh(invoice)
    return {"message": "Status updated", "status": invoice.status}
