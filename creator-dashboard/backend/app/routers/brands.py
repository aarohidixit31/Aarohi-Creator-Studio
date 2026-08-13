from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload
from typing import List
from .. import models, schemas
from ..database import get_db
from ..auth import get_current_admin

router = APIRouter(prefix="/api/brands", tags=["brands"])

ACTIVE_COLLAB_STATUSES = {
    "new", "in_discussion", "negotiating", "confirmed", "agreement_invoice",
    "script_approved", "shoot_done", "draft_submitted", "content_posted",
}


def _brand_summary(brand: models.Brand):
    collabs = brand.collabs or []
    invoices = brand.invoices or []
    activity_dates = [
        item.created_at for item in [*collabs, *invoices]
        if item.created_at is not None
    ]
    return {
        "id": brand.id,
        "name": brand.name,
        "contact_person": brand.contact_person,
        "email": brand.email,
        "phone": brand.phone,
        "notes": brand.notes,
        "created_at": brand.created_at,
        "collaboration_count": len(collabs),
        "active_collaboration_count": sum(
            collab.status in ACTIVE_COLLAB_STATUSES and collab.archived_at is None
            for collab in collabs
        ),
        "invoice_count": len(invoices),
        "total_invoiced": sum(invoice.total or 0 for invoice in invoices),
        "total_received": sum(
            invoice.total or 0 for invoice in invoices if invoice.status == "paid"
        ),
        "outstanding_amount": sum(
            invoice.total or 0
            for invoice in invoices
            if invoice.status in ("sent", "overdue")
        ),
        "last_activity_at": max(activity_dates) if activity_dates else brand.created_at,
    }


@router.get("/", response_model=List[schemas.BrandOut])
def list_brands(db: Session = Depends(get_db), admin=Depends(get_current_admin)):
    return db.query(models.Brand).order_by(models.Brand.name).all()


@router.post("/", response_model=schemas.BrandOut)
def create_brand(payload: schemas.BrandCreate, db: Session = Depends(get_db), admin=Depends(get_current_admin)):
    brand = models.Brand(**payload.model_dump())
    db.add(brand)
    db.commit()
    db.refresh(brand)
    return brand


@router.get("/directory", response_model=List[schemas.BrandDirectoryOut])
def brand_directory(db: Session = Depends(get_db), admin=Depends(get_current_admin)):
    brands = (
        db.query(models.Brand)
        .options(joinedload(models.Brand.collabs), joinedload(models.Brand.invoices))
        .all()
    )
    summaries = [_brand_summary(brand) for brand in brands]
    return sorted(
        summaries,
        key=lambda item: item["last_activity_at"] or item["created_at"],
        reverse=True,
    )


@router.get("/{brand_id}", response_model=schemas.BrandDetailOut)
def get_brand(brand_id: int, db: Session = Depends(get_db), admin=Depends(get_current_admin)):
    brand = (
        db.query(models.Brand)
        .options(joinedload(models.Brand.collabs), joinedload(models.Brand.invoices))
        .filter(models.Brand.id == brand_id)
        .first()
    )
    if not brand:
        raise HTTPException(404, "Brand not found")
    result = _brand_summary(brand)
    result["collabs"] = sorted(
        brand.collabs, key=lambda item: item.created_at, reverse=True
    )
    result["invoices"] = sorted(
        brand.invoices, key=lambda item: item.created_at, reverse=True
    )
    return result


@router.patch("/{brand_id}", response_model=schemas.BrandOut)
def update_brand(
    brand_id: int,
    payload: schemas.BrandUpdate,
    db: Session = Depends(get_db),
    admin=Depends(get_current_admin),
):
    brand = db.query(models.Brand).filter(models.Brand.id == brand_id).first()
    if not brand:
        raise HTTPException(404, "Brand not found")

    updates = payload.model_dump(exclude_unset=True)
    if "name" in updates and not updates["name"].strip():
        raise HTTPException(400, "Brand name cannot be empty")
    for field, value in updates.items():
        setattr(brand, field, value.strip() if isinstance(value, str) else value)
    db.commit()
    db.refresh(brand)
    return brand
