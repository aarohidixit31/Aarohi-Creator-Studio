from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session, joinedload

from .. import models, schemas
from ..auth import get_current_admin
from ..database import get_db

router = APIRouter(prefix="/api/content", tags=["content"])
PLATFORMS = {"Instagram", "YouTube", "LinkedIn", "Other"}
PLATFORM_NAMES = {name.casefold(): name for name in PLATFORMS}


def _platform_name(value: str) -> str:
    platform = PLATFORM_NAMES.get(value.strip().casefold())
    if not platform:
        raise HTTPException(400, f"Platform must be one of {sorted(PLATFORMS)}")
    return platform


def _get_content(db: Session, content_id: int) -> models.ContentItem:
    item = (
        db.query(models.ContentItem)
        .options(joinedload(models.ContentItem.brand), joinedload(models.ContentItem.collab))
        .filter(models.ContentItem.id == content_id)
        .first()
    )
    if not item:
        raise HTTPException(404, "Content item not found")
    return item


def _payload(item: models.ContentItem) -> dict:
    collab_label = None
    if item.collab:
        collab_label = (
            item.collab.campaign_type
            or item.collab.deliverables
            or f"Collaboration #{item.collab.id}"
        )
    return {
        "id": item.id,
        "brand_id": item.brand_id,
        "collab_id": item.collab_id,
        "brand": item.brand,
        "collab_label": collab_label,
        "platform": item.platform,
        "title": item.title,
        "content_url": item.content_url,
        "thumbnail_url": item.thumbnail_url,
        "published_at": item.published_at,
        "objective": item.objective,
        "results": item.results,
        "notes": item.notes,
        "metrics": item.metrics or {},
        "featured": bool(item.featured),
        "created_at": item.created_at,
    }


def _validate_links(db: Session, brand_id: int | None, collab_id: int | None):
    brand = None
    collab = None
    if brand_id:
        brand = db.query(models.Brand).filter(models.Brand.id == brand_id).first()
        if not brand:
            raise HTTPException(404, "Brand not found")
    if collab_id:
        collab = db.query(models.Collab).filter(models.Collab.id == collab_id).first()
        if not collab:
            raise HTTPException(404, "Collaboration not found")
        if brand and collab.brand_id != brand.id:
            raise HTTPException(400, "The selected collaboration belongs to another brand")
        brand = brand or collab.brand
    return brand, collab


@router.get("/case-studies", response_model=list[schemas.ContentOut])
def public_case_studies(db: Session = Depends(get_db)):
    items = (
        db.query(models.ContentItem)
        .options(joinedload(models.ContentItem.brand), joinedload(models.ContentItem.collab))
        .filter(models.ContentItem.featured.is_(True))
        .order_by(models.ContentItem.published_at.desc(), models.ContentItem.created_at.desc())
        .all()
    )
    return [_payload(item) for item in items]


@router.get("/summary", response_model=schemas.ContentLibrarySummary)
def content_summary(db: Session = Depends(get_db), admin=Depends(get_current_admin)):
    items = db.query(models.ContentItem).all()
    views = [int((item.metrics or {}).get("views") or 0) for item in items]
    reach = [int((item.metrics or {}).get("reach") or 0) for item in items]
    engagement = [
        float((item.metrics or {}).get("engagement_rate"))
        for item in items
        if (item.metrics or {}).get("engagement_rate") is not None
    ]
    top_index = max(range(len(items)), key=lambda index: views[index], default=None)
    return {
        "content_count": len(items),
        "featured_count": sum(bool(item.featured) for item in items),
        "total_views": sum(views),
        "total_reach": sum(reach),
        "average_engagement_rate": sum(engagement) / len(engagement) if engagement else 0,
        "top_content_id": items[top_index].id if top_index is not None else None,
    }


@router.get("/", response_model=list[schemas.ContentOut])
def list_content(db: Session = Depends(get_db), admin=Depends(get_current_admin)):
    items = (
        db.query(models.ContentItem)
        .options(joinedload(models.ContentItem.brand), joinedload(models.ContentItem.collab))
        .order_by(models.ContentItem.published_at.desc(), models.ContentItem.created_at.desc())
        .all()
    )
    return [_payload(item) for item in items]


@router.post("/", response_model=schemas.ContentOut, status_code=201)
def create_content(
    payload: schemas.ContentCreate,
    db: Session = Depends(get_db),
    admin=Depends(get_current_admin),
):
    platform = _platform_name(payload.platform)
    if not payload.title.strip():
        raise HTTPException(400, "Content title is required")
    brand, collab = _validate_links(db, payload.brand_id, payload.collab_id)
    item = models.ContentItem(
        **payload.model_dump(exclude={"metrics", "brand_id", "collab_id", "platform", "title"}),
        brand_id=brand.id if brand else None,
        collab_id=collab.id if collab else None,
        platform=platform,
        title=payload.title.strip(),
        metrics=payload.metrics.model_dump(),
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    item.brand = brand
    item.collab = collab
    return _payload(item)


@router.patch("/{content_id}", response_model=schemas.ContentOut)
def update_content(
    content_id: int,
    payload: schemas.ContentUpdate,
    db: Session = Depends(get_db),
    admin=Depends(get_current_admin),
):
    item = _get_content(db, content_id)
    updates = payload.model_dump(exclude_unset=True)
    next_brand_id = updates.get("brand_id", item.brand_id)
    next_collab_id = updates.get("collab_id", item.collab_id)
    brand, collab = _validate_links(db, next_brand_id, next_collab_id)
    if "platform" in updates:
        updates["platform"] = _platform_name(updates["platform"])
    if "title" in updates:
        if not updates["title"].strip():
            raise HTTPException(400, "Content title is required")
        updates["title"] = updates["title"].strip()
    if "metrics" in updates and hasattr(updates["metrics"], "model_dump"):
        updates["metrics"] = updates["metrics"].model_dump()
    updates["brand_id"] = brand.id if brand else None
    updates["collab_id"] = collab.id if collab else None
    for field, value in updates.items():
        setattr(item, field, value)
    db.commit()
    db.refresh(item)
    item.brand = brand
    item.collab = collab
    return _payload(item)


@router.delete("/{content_id}", status_code=204)
def delete_content(
    content_id: int,
    db: Session = Depends(get_db),
    admin=Depends(get_current_admin),
):
    item = _get_content(db, content_id)
    db.delete(item)
    db.commit()
    return Response(status_code=204)
