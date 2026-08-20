import os
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import Response
from jinja2 import Environment, FileSystemLoader
from sqlalchemy.orm import Session, joinedload

from .. import models, schemas
from ..auth import get_current_admin
from ..database import get_db
from ..services import email as email_service
from ..services.storage import store_document


router = APIRouter(prefix="/api/agreements", tags=["agreements"])
TEMPLATE_DIR = Path(__file__).resolve().parents[1] / "templates"
jinja_env = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)), autoescape=True)
UPLOAD_DIR = Path(__file__).resolve().parents[2] / "uploads" / "agreements"
MAX_SIGNED_FILE_BYTES = 10 * 1024 * 1024
ALLOWED_SIGNED_TYPES = {
    "application/pdf": ".pdf",
    "image/jpeg": ".jpg",
    "image/png": ".png",
}


def _collab(db: Session, collab_id: int) -> models.Collab:
    collab = (
        db.query(models.Collab)
        .options(joinedload(models.Collab.brand))
        .filter(models.Collab.id == collab_id)
        .first()
    )
    if not collab:
        raise HTTPException(404, "Collaboration not found")
    return collab


def _agreement_number(collab: models.Collab) -> str:
    year = (collab.created_at or datetime.now(timezone.utc)).year
    return f"AGR-{year}-{collab.id:04d}"


def _agreement_data(collab: models.Collab) -> dict:
    details = dict(collab.details or {})
    stored = dict(details.get("agreement") or {})
    defaults = {
        "agreement_number": _agreement_number(collab),
        "status": "not_created",
        "effective_date": collab.created_at.isoformat() if collab.created_at else None,
        "termination_date": collab.deadline.isoformat() if collab.deadline else None,
        "deliverables": collab.deliverables,
        "timeline": "As mutually agreed in writing",
        "total_amount": collab.budget,
        "payment_structure": "50% advance payment, 50% final payment",
        "payment_due_days": 5,
        "revision_limit": 2,
        "content_live_months": 6,
        "usage_rights": "Organic reposting on the Brand's owned social channels with prior consent and proper creator credit. Paid usage, whitelisting, boosting, and third-party licensing require a separate written agreement.",
        "additional_terms": None,
        "generated_at": None,
        "sent_at": None,
        "signed_at": None,
        "signed_file_url": None,
        "email_message_id": None,
    }
    defaults.update(stored)
    return defaults


def _save_agreement(collab: models.Collab, agreement: dict, action: str, detail: str) -> None:
    details = dict(collab.details or {})
    activity = list(details.get("activity_log") or [])
    activity.append({
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "action": action,
        "detail": detail,
        "from_status": None,
        "to_status": None,
    })
    details["agreement"] = agreement
    details["activity_log"] = activity[-100:]
    collab.details = details


def _render_pdf(collab: models.Collab, agreement: dict) -> bytes:
    from weasyprint import HTML

    template = jinja_env.get_template("agreement.html")
    html = template.render(
        creator_name=os.getenv("CREATOR_NAME", "Aarohi Dixit"),
        creator_tagline=os.getenv("CREATOR_TAGLINE", "Tech Content Creator"),
        creator_email=os.getenv("CREATOR_EMAIL", os.getenv("ADMIN_EMAIL", "aarohi.inframe@gmail.com")),
        brand=collab.brand,
        collab=collab,
        agreement=agreement,
        effective_date=_display_date(agreement.get("effective_date")),
        termination_date=_display_date(agreement.get("termination_date")),
    )
    return HTML(string=html).write_pdf()


def _display_date(value) -> str:
    if not value:
        return "To be mutually agreed"
    if isinstance(value, str):
        value = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return value.strftime("%d %B %Y")


@router.get("/{collab_id}", response_model=schemas.AgreementOut)
def get_agreement(collab_id: int, db: Session = Depends(get_db), admin=Depends(get_current_admin)):
    return _agreement_data(_collab(db, collab_id))


@router.put("/{collab_id}", response_model=schemas.AgreementOut)
def update_agreement(
    collab_id: int,
    payload: schemas.AgreementUpdate,
    db: Session = Depends(get_db),
    admin=Depends(get_current_admin),
):
    if (
        payload.payment_due_days < 0
        or payload.revision_limit < 0
        or payload.content_live_months < 0
        or (payload.total_amount is not None and payload.total_amount < 0)
    ):
        raise HTTPException(400, "Agreement numeric terms cannot be negative")
    collab = _collab(db, collab_id)
    agreement = _agreement_data(collab)
    updates = payload.model_dump(mode="json")
    agreement.update(updates)
    agreement["status"] = "draft" if agreement["status"] == "not_created" else agreement["status"]
    agreement["generated_at"] = datetime.now(timezone.utc).isoformat()
    _save_agreement(collab, agreement, "agreement_updated", "Agreement terms saved")
    db.commit()
    return agreement


@router.get("/{collab_id}/pdf")
def agreement_pdf(collab_id: int, db: Session = Depends(get_db), admin=Depends(get_current_admin)):
    collab = _collab(db, collab_id)
    agreement = _agreement_data(collab)
    return Response(
        content=_render_pdf(collab, agreement),
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{agreement["agreement_number"]}.pdf"'},
    )


@router.post("/{collab_id}/send")
def send_agreement(collab_id: int, db: Session = Depends(get_db), admin=Depends(get_current_admin)):
    collab = _collab(db, collab_id)
    if not collab.brand or not collab.brand.email:
        raise HTTPException(400, "Add a brand email before sending the agreement")
    agreement = _agreement_data(collab)
    if agreement["status"] == "not_created":
        raise HTTPException(400, "Save the agreement draft before sending it")
    result = email_service.send_agreement_delivery(
        recipient=collab.brand.email,
        contact_person=collab.brand.contact_person,
        brand_name=collab.brand.name,
        agreement_number=agreement["agreement_number"],
        pdf_bytes=_render_pdf(collab, agreement),
        idempotency_key=f"agreement-{collab.id}-{int(datetime.now(timezone.utc).timestamp())}",
    )
    if not result.sent:
        raise HTTPException(503 if result.disabled else 502, result.error or "Agreement email failed")
    now = datetime.now(timezone.utc).isoformat()
    agreement.update({"status": "sent", "sent_at": now, "email_message_id": result.message_id})
    _save_agreement(collab, agreement, "agreement_sent", f"Agreement emailed to {collab.brand.email}")
    db.commit()
    return {"message": f"Agreement emailed to {collab.brand.email}", "agreement": agreement}


@router.post("/{collab_id}/signed", response_model=schemas.AgreementOut)
async def upload_signed_agreement(
    collab_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    admin=Depends(get_current_admin),
):
    content_type = (file.content_type or "").casefold()
    extension = ALLOWED_SIGNED_TYPES.get(content_type)
    if not extension:
        raise HTTPException(400, "Upload a signed PDF, JPG, or PNG file")
    contents = await file.read(MAX_SIGNED_FILE_BYTES + 1)
    if not contents or len(contents) > MAX_SIGNED_FILE_BYTES:
        raise HTTPException(400, "Signed agreement must be between 1 byte and 10 MB")
    collab = _collab(db, collab_id)
    try:
        stored = store_document(
            contents,
            original_filename=file.filename or f"signed-agreement{extension}",
            content_type=content_type,
            local_directory=UPLOAD_DIR,
            local_url_prefix="/api/uploads/agreements",
            local_extension=extension,
        )
    except RuntimeError as exc:
        raise HTTPException(502, str(exc)) from exc
    agreement = _agreement_data(collab)
    agreement.update({
        "status": "signed",
        "signed_at": datetime.now(timezone.utc).isoformat(),
        "signed_file_url": stored.url,
    })
    _save_agreement(collab, agreement, "agreement_signed", "Signed agreement uploaded")
    db.commit()
    return agreement
