import math
from datetime import datetime, timezone
from statistics import median

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session, joinedload

from .. import models, schemas
from ..auth import get_current_admin
from ..database import get_db
from ..services.content_sync import refresh_imported_youtube_content, sync_youtube_content, youtube_catalog
from ..services.instagram_content_sync import instagram_catalog, refresh_imported_instagram_content, sync_instagram_content

router = APIRouter(prefix="/api/content", tags=["content"])
PLATFORMS = {"Instagram", "YouTube", "LinkedIn", "Other"}
PLATFORM_NAMES = {name.casefold(): name for name in PLATFORMS}
VERIFICATION_METHODS = {"manual", "screenshot", "api"}


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


def _number(metrics: dict, field: str) -> float:
    try:
        return max(0, float(metrics.get(field) or 0))
    except (TypeError, ValueError):
        return 0


def _engagement_rate(metrics: dict) -> float:
    supplied = _number(metrics, "engagement_rate")
    if supplied:
        return supplied
    reach = _number(metrics, "reach") or _number(metrics, "views")
    if not reach:
        return 0
    interactions = sum(_number(metrics, field) for field in ("likes", "comments", "saves", "shares"))
    return round(interactions / reach * 100, 2)


def _baselines(items: list[models.ContentItem]) -> dict[str, dict]:
    grouped: dict[str, list[dict]] = {}
    for item in items:
        grouped.setdefault(item.platform, []).append(item.metrics or {})
    result = {}
    for platform, metrics_list in grouped.items():
        def midpoint(values):
            nonzero = [value for value in values if value > 0]
            return float(median(nonzero)) if nonzero else 0
        result[platform] = {
            "views": midpoint([_number(metrics, "views") for metrics in metrics_list]),
            "reach": midpoint([_number(metrics, "reach") for metrics in metrics_list]),
            "engagement": midpoint([_engagement_rate(metrics) for metrics in metrics_list]),
        }
    return result


def _performance(item: models.ContentItem, baseline: dict | None) -> dict:
    metrics = item.metrics or {}
    baseline = baseline or {}
    primary = _number(metrics, "views") or _number(metrics, "reach")
    primary_baseline = baseline.get("views") or baseline.get("reach") or 0
    multiplier = primary / primary_baseline if primary and primary_baseline else 0
    engagement = _engagement_rate(metrics)
    engagement_baseline = float(baseline.get("engagement") or 0)
    engagement_multiplier = engagement / engagement_baseline if engagement and engagement_baseline else 0
    if not multiplier and not engagement_multiplier:
        return {
            "performance_score": 0,
            "performance_multiplier": 0,
            "performance_label": "Add performance data",
            "calculated_engagement_rate": engagement,
        }
    score = 50
    if multiplier:
        score += max(-30, min(35, math.log2(max(multiplier, .2)) * 22))
    if engagement_multiplier:
        score += max(-10, min(15, math.log2(max(engagement_multiplier, .25)) * 10))
    score = max(1, min(100, round(score)))
    if multiplier >= 2:
        label = "Breakout performer"
    elif multiplier >= 1.35:
        label = "High performer"
    elif multiplier >= 1.08:
        label = "Above average"
    elif multiplier >= .75:
        label = "On track"
    else:
        label = "Building"
    return {
        "performance_score": score,
        "performance_multiplier": round(multiplier, 2),
        "performance_label": label,
        "calculated_engagement_rate": engagement,
    }


def _normalized_metrics(metrics) -> dict:
    values = metrics.model_dump(mode="json") if hasattr(metrics, "model_dump") else dict(metrics or {})
    method = str(values.get("verification_method") or "manual").casefold()
    if method not in VERIFICATION_METHODS:
        raise HTTPException(400, "Performance verification must be manual, screenshot, or api")
    values["verification_method"] = method
    tracked = ("views", "reach", "likes", "comments", "saves", "shares", "conversions")
    if not values.get("measured_at") and any(values.get(field) is not None for field in tracked):
        values["measured_at"] = datetime.now(timezone.utc).isoformat()
    return values


def _payload(item: models.ContentItem, baseline: dict | None = None, *, public: bool = False) -> dict:
    collab_label = None
    if item.collab:
        collab_label = (
            item.collab.campaign_type
            or item.collab.deliverables
            or f"Collaboration #{item.collab.id}"
        )
    metrics = dict(item.metrics or {})
    if public:
        for private_field in ("proof_url", "external_id", "sync_source", "review_status"):
            metrics.pop(private_field, None)
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
        "notes": None if public else item.notes,
        "metrics": metrics,
        "featured": bool(item.featured),
        "created_at": item.created_at,
        **_performance(item, baseline),
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
    baselines = _baselines(db.query(models.ContentItem).all())
    payloads = [_payload(item, baselines.get(item.platform), public=True) for item in items]
    return sorted(payloads, key=lambda item: (item["performance_score"], item["published_at"] or item["created_at"]), reverse=True)


@router.get("/summary", response_model=schemas.ContentLibrarySummary)
def content_summary(db: Session = Depends(get_db), admin=Depends(get_current_admin)):
    items = db.query(models.ContentItem).all()
    views = [int((item.metrics or {}).get("views") or 0) for item in items]
    reach = [int((item.metrics or {}).get("reach") or 0) for item in items]
    engagement = [_engagement_rate(item.metrics or {}) for item in items]
    engagement = [value for value in engagement if value]
    baselines = _baselines(items)
    performance = [_performance(item, baselines.get(item.platform)) for item in items]
    top_index = max(range(len(items)), key=lambda index: performance[index]["performance_score"], default=None)
    return {
        "content_count": len(items),
        "featured_count": sum(bool(item.featured) for item in items),
        "total_views": sum(views),
        "total_reach": sum(reach),
        "average_engagement_rate": sum(engagement) / len(engagement) if engagement else 0,
        "top_content_id": items[top_index].id if top_index is not None else None,
        "high_performer_count": sum(item["performance_label"] in {"Breakout performer", "High performer"} for item in performance),
        "verified_count": sum((item.metrics or {}).get("verification_method") in {"api", "screenshot"} for item in items),
        "imported_count": sum(bool((item.metrics or {}).get("sync_source")) for item in items),
        "pending_review_count": sum((item.metrics or {}).get("review_status") == "pending" for item in items),
    }


@router.get("/", response_model=list[schemas.ContentOut])
def list_content(db: Session = Depends(get_db), admin=Depends(get_current_admin)):
    items = (
        db.query(models.ContentItem)
        .options(joinedload(models.ContentItem.brand), joinedload(models.ContentItem.collab))
        .order_by(models.ContentItem.published_at.desc(), models.ContentItem.created_at.desc())
        .all()
    )
    baselines = _baselines(items)
    return [_payload(item, baselines.get(item.platform)) for item in items]


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
        metrics=_normalized_metrics(payload.metrics),
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    item.brand = brand
    item.collab = collab
    baselines = _baselines(db.query(models.ContentItem).all())
    return _payload(item, baselines.get(item.platform))


@router.get("/youtube/catalog", response_model=schemas.YouTubeCatalogOut)
def discover_youtube_content(
    db: Session = Depends(get_db),
    admin=Depends(get_current_admin),
):
    try:
        return youtube_catalog(db)
    except RuntimeError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/youtube/import", response_model=schemas.ContentSyncOut)
def import_selected_youtube_content(
    payload: schemas.YouTubeImportRequest,
    db: Session = Depends(get_db),
    admin=Depends(get_current_admin),
):
    try:
        return sync_youtube_content(db, payload.video_ids)
    except RuntimeError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/youtube/refresh", response_model=schemas.ContentSyncOut)
def refresh_youtube_content(
    db: Session = Depends(get_db),
    admin=Depends(get_current_admin),
):
    try:
        return refresh_imported_youtube_content(db)
    except RuntimeError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.get("/instagram/catalog", response_model=schemas.InstagramCatalogOut)
def discover_instagram_content(
    db: Session = Depends(get_db),
    admin=Depends(get_current_admin),
):
    try:
        return instagram_catalog(db)
    except RuntimeError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/instagram/import", response_model=schemas.ContentSyncOut)
def import_selected_instagram_content(
    payload: schemas.InstagramImportRequest,
    db: Session = Depends(get_db),
    admin=Depends(get_current_admin),
):
    try:
        return sync_instagram_content(db, payload.media_ids)
    except RuntimeError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/instagram/refresh", response_model=schemas.ContentSyncOut)
def refresh_instagram_content(
    db: Session = Depends(get_db),
    admin=Depends(get_current_admin),
):
    try:
        return refresh_imported_instagram_content(db)
    except RuntimeError as exc:
        raise HTTPException(400, str(exc)) from exc


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
    if "metrics" in updates:
        updates["metrics"] = _normalized_metrics(updates["metrics"])
    updates["brand_id"] = brand.id if brand else None
    updates["collab_id"] = collab.id if collab else None
    for field, value in updates.items():
        setattr(item, field, value)
    db.commit()
    db.refresh(item)
    item.brand = brand
    item.collab = collab
    baselines = _baselines(db.query(models.ContentItem).all())
    return _payload(item, baselines.get(item.platform))


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
