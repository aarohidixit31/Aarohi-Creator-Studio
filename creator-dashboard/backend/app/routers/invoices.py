import os
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session, joinedload
from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML
from .. import models, schemas
from ..database import get_db
from ..auth import get_current_admin

router = APIRouter(prefix="/api/invoices", tags=["invoices"])

TEMPLATE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates")
jinja_env = Environment(loader=FileSystemLoader(TEMPLATE_DIR))

# --- Edit these to match your details, or move into MediaKitContent later ---
CREATOR_NAME = os.getenv("CREATOR_NAME", "Aarohi Dixit")
CREATOR_TAGLINE = os.getenv("CREATOR_TAGLINE", "Tech Content Creator")
CREATOR_EMAIL = os.getenv("CREATOR_EMAIL", os.getenv("ADMIN_EMAIL", "aarohi.inframe@gmail.com"))
PAYMENT_DETAILS = os.getenv("PAYMENT_DETAILS", "UPI: yourupi@bank | Bank transfer details on request")


def _generate_invoice_number(db: Session) -> str:
    year = datetime.utcnow().year
    count_this_year = (
        db.query(models.Invoice)
        .filter(models.Invoice.invoice_number.like(f"INV-{year}-%"))
        .count()
    )
    return f"INV-{year}-{count_this_year + 1:03d}"


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
    invoice = db.query(models.Invoice).filter(models.Invoice.id == invoice_id).first()
    if not invoice:
        raise HTTPException(404, "Invoice not found")
    brand = db.query(models.Brand).filter(models.Brand.id == invoice.brand_id).first()

    template = jinja_env.get_template("invoice.html")
    html_content = template.render(
        creator_name=CREATOR_NAME,
        creator_tagline=CREATOR_TAGLINE,
        creator_email=CREATOR_EMAIL,
        invoice_number=invoice.invoice_number,
        invoice_status=invoice.status,
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

    pdf_bytes = HTML(string=html_content).write_pdf()
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{invoice.invoice_number}.pdf"'},
    )


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
        invoice.paid_at = datetime.utcnow()
    else:
        invoice.paid_at = None
    invoice.status = status
    db.commit()
    db.refresh(invoice)
    return {"message": "Status updated", "status": invoice.status}
