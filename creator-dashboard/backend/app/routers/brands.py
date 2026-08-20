import csv
import hashlib
import io
import re
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload
from typing import List
from .. import models, schemas
from ..database import get_db
from ..auth import get_current_admin

router = APIRouter(prefix="/api/brands", tags=["brands"])

MAX_CSV_BYTES = 2 * 1024 * 1024
IMPORT_STATUSES = {
    "new": "new", "in discussion": "in_discussion", "discussion": "in_discussion",
    "negotiating": "negotiating", "confirmed": "confirmed",
    "agreement & invoice": "agreement_invoice", "agreement and invoice": "agreement_invoice",
    "script approved": "script_approved", "shoot done": "shoot_done",
    "draft submitted": "draft_submitted", "content posted": "content_posted",
    "payment received": "payment_received", "payment recieved": "payment_received",
    "closed": "closed",
}

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


def _clean(row: dict, key: str) -> str:
    return str(row.get(key) or "").strip()


def _parse_date(value: str) -> datetime | None:
    if not value:
        return None
    for pattern in (None, "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d", "%d %b %Y", "%d %B %Y"):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00")) if pattern is None else datetime.strptime(value, pattern)
            return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed.astimezone(timezone.utc)
        except ValueError:
            continue
    raise ValueError(f"Invalid date '{value}'. Use YYYY-MM-DD or DD/MM/YYYY")


def _parse_budget(value: str) -> float | None:
    if not value:
        return None
    cleaned = re.sub(r"[^0-9.\-]", "", value)
    if not cleaned:
        raise ValueError(f"Invalid budget '{value}'")
    return float(cleaned)


def _truthy(value: str, default: bool = False) -> bool:
    normalized = str(value or "").strip().casefold()
    if not normalized:
        return default
    if normalized in {"yes", "y", "true", "1", "publish", "featured"}:
        return True
    if normalized in {"no", "n", "false", "0"}:
        return False
    raise ValueError(f"Invalid yes/no value '{value}'")


def _add_media_kit_collab(db: Session, item: dict) -> bool:
    """Add a collaboration to the working media-kit draft without publishing it."""
    from .media_kit import _serialize

    content = db.query(models.MediaKitContent).first()
    if not content:
        content = models.MediaKitContent(id=1)
        db.add(content)
        db.flush()
    draft = dict(content.draft_content or _serialize(content))
    past_collabs = list(draft.get("past_collabs") or [])
    item_url = str(item.get("content_url") or "").rstrip("/").casefold()
    duplicate = next((existing for existing in past_collabs if (
        str(existing.get("brand") or "").strip().casefold() == str(item.get("brand") or "").strip().casefold()
        and str(existing.get("content_url") or "").rstrip("/").casefold() == item_url
    )), None)
    if duplicate:
        for key, value in item.items():
            if value and not duplicate.get(key):
                duplicate[key] = value
        content.draft_content = {**draft, "past_collabs": past_collabs}
        return False
    past_collabs.append(item)
    content.draft_content = {**draft, "past_collabs": past_collabs}
    return True


def _import_key(row: dict, email: str, brand_name: str) -> str:
    source = _clean(row, "source_id")
    if source:
        raw = f"source:{source.casefold()}"
    else:
        fields = [
            email or brand_name.casefold(), _clean(row, "campaign_type").casefold(),
            _clean(row, "status").casefold(), _clean(row, "budget"),
            _clean(row, "deadline"), _clean(row, "content_link").rstrip("/").casefold(),
        ]
        raw = "|".join(fields)
    return "csv:" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


@router.get("/", response_model=List[schemas.BrandOut])
def list_brands(db: Session = Depends(get_db), admin=Depends(get_current_admin)):
    return db.query(models.Brand).order_by(models.Brand.name).all()


@router.post("/", response_model=schemas.BrandOut)
def create_brand(payload: schemas.BrandCreate, db: Session = Depends(get_db), admin=Depends(get_current_admin)):
    email = str(payload.email or "").strip().casefold()
    brand = None
    if email:
        brand = db.query(models.Brand).filter(func.lower(func.trim(models.Brand.email)) == email).first()
    if not brand:
        brand = db.query(models.Brand).filter(func.lower(func.trim(models.Brand.name)) == payload.name.strip().casefold()).first()
    if brand:
        for field in ("contact_person", "email", "phone", "notes"):
            value = getattr(payload, field)
            if value and not getattr(brand, field):
                setattr(brand, field, str(value).strip())
        db.commit()
        db.refresh(brand)
        return brand
    brand = models.Brand(**payload.model_dump())
    db.add(brand)
    db.commit()
    db.refresh(brand)
    return brand


@router.post("/import-history")
async def import_brand_history(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    admin=Depends(get_current_admin),
):
    """Import historical brand collaborations from a safe, repeatable CSV."""
    if not (file.filename or "").lower().endswith(".csv"):
        raise HTTPException(400, "Upload a .csv file")
    contents = await file.read(MAX_CSV_BYTES + 1)
    if len(contents) > MAX_CSV_BYTES:
        raise HTTPException(413, "CSV must be smaller than 2 MB")
    try:
        text = contents.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise HTTPException(400, "CSV must be UTF-8 encoded") from exc
    reader = csv.DictReader(io.StringIO(text))
    headers = {str(value or "").strip().casefold() for value in (reader.fieldnames or [])}
    if "brand_name" not in headers:
        raise HTTPException(400, "CSV must include a brand_name column")

    summary = {
        "rows_received": 0, "brands_created": 0, "brands_reused": 0,
        "collabs_created": 0, "duplicates_skipped": 0, "rows_failed": 0,
        "media_kit_added": 0, "media_kit_reused": 0,
        "errors": [],
    }
    seen_brands = set()
    seen_keys = {
        str((collab.details or {}).get("import_key"))
        for collab in db.query(models.Collab).all()
        if (collab.details or {}).get("import_key")
    }
    for row_number, raw_row in enumerate(reader, start=2):
        summary["rows_received"] += 1
        row = {str(key or "").strip().casefold(): value for key, value in raw_row.items()}
        try:
            brand_name = _clean(row, "brand_name")
            if not brand_name:
                raise ValueError("Brand name is required")
            email = _clean(row, "email").casefold()
            if email and not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
                raise ValueError(f"Invalid email '{email}'")
            status_label = re.sub(r"[_\-]+", " ", _clean(row, "status").casefold()).strip() or "closed"
            status = IMPORT_STATUSES.get(status_label)
            if not status:
                raise ValueError(f"Unknown status '{_clean(row, 'status')}'")
            deadline = _parse_date(_clean(row, "deadline"))
            created_at = _parse_date(_clean(row, "created_at"))
            budget = _parse_budget(_clean(row, "budget"))
            content_url = _clean(row, "content_link")
            show_on_media_kit = _truthy(_clean(row, "show_on_media_kit"), default=False)
            if content_url and not re.match(r"^https?://", content_url, re.IGNORECASE):
                raise ValueError("Content link must start with http:// or https://")

            brand = None
            if email:
                brand = db.query(models.Brand).filter(func.lower(func.trim(models.Brand.email)) == email).order_by(models.Brand.id).first()
            if not brand:
                brand = db.query(models.Brand).filter(func.lower(func.trim(models.Brand.name)) == brand_name.casefold()).order_by(models.Brand.id).first()
            brand_identity = f"email:{email}" if email else f"name:{brand_name.casefold()}"
            if not brand:
                brand = models.Brand(
                    name=brand_name,
                    contact_person=_clean(row, "contact_person") or None,
                    email=email or None,
                    phone=_clean(row, "phone") or None,
                    notes=_clean(row, "brand_notes") or None,
                )
                db.add(brand)
                db.flush()
                summary["brands_created"] += 1
            else:
                if brand_identity not in seen_brands:
                    summary["brands_reused"] += 1
                if not brand.contact_person and _clean(row, "contact_person"):
                    brand.contact_person = _clean(row, "contact_person")
                if not brand.phone and _clean(row, "phone"):
                    brand.phone = _clean(row, "phone")
                if not brand.email and email:
                    brand.email = email
            seen_brands.add(brand_identity)

            key = _import_key(row, email, brand_name)
            if key in seen_keys:
                summary["duplicates_skipped"] += 1
                continue
            details = {
                "import_key": key,
                "import_source": file.filename,
                "priority": _clean(row, "priority").casefold() or "normal",
                "assignee": _clean(row, "assignee").casefold() or "unassigned",
                "waiting_on": "none",
                "next_action": _clean(row, "next_action") or None,
                "activity_log": [{
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "action": "history_imported",
                    "detail": f"Imported from {file.filename}",
                    "to_status": status,
                }],
            }
            collab = models.Collab(
                brand_id=brand.id,
                status=status,
                campaign_type=_clean(row, "campaign_type") or "Historical collaboration",
                deliverables=_clean(row, "deliverables") or None,
                budget=budget,
                deadline=deadline,
                brief=_clean(row, "brief") or None,
                content_link=_clean(row, "content_link") or None,
                notes=_clean(row, "notes") or None,
                details=details,
            )
            if created_at:
                collab.created_at = created_at
            db.add(collab)
            db.flush()
            seen_keys.add(key)
            summary["collabs_created"] += 1

            if show_on_media_kit:
                added = _add_media_kit_collab(db, {
                    "brand": brand.name,
                    "logo_url": _clean(row, "media_kit_logo_url") or None,
                    "image_url": _clean(row, "media_kit_image_url") or None,
                    "content_url": content_url or None,
                    "summary": _clean(row, "media_kit_summary") or _clean(row, "results") or collab.deliverables or collab.campaign_type,
                    "visible": True,
                })
                summary["media_kit_added" if added else "media_kit_reused"] += 1
        except (ValueError, TypeError) as exc:
            summary["rows_failed"] += 1
            if len(summary["errors"]) < 25:
                summary["errors"].append({"row": row_number, "message": str(exc)})
    db.commit()
    return summary


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


@router.post("/{brand_id}/collabs/{collab_id}/media-kit")
def add_collaboration_to_media_kit(
    brand_id: int,
    collab_id: int,
    db: Session = Depends(get_db),
    admin=Depends(get_current_admin),
):
    brand = db.query(models.Brand).filter(models.Brand.id == brand_id).first()
    collab = db.query(models.Collab).filter(
        models.Collab.id == collab_id,
        models.Collab.brand_id == brand_id,
    ).first()
    if not brand or not collab:
        raise HTTPException(404, "Brand collaboration not found")

    resources = list((collab.details or {}).get("resource_links") or [])
    image = next((item.get("url") for item in resources if (
        str(item.get("content_type") or "").startswith("image/")
        or str(item.get("kind") or "").casefold() in {"image", "screenshot", "thumbnail"}
    )), None)
    added = _add_media_kit_collab(db, {
        "brand": brand.name,
        "logo_url": None,
        "image_url": image,
        "content_url": collab.content_link,
        "summary": collab.deliverables or collab.campaign_type or collab.brief,
        "visible": True,
    })
    db.commit()
    return {
        "added": added,
        "message": "Added to the media-kit draft" if added else "Media-kit draft already contains this collaboration",
        "preview_url": "/admin/media-kit/preview",
    }


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
