from io import BytesIO
from pathlib import Path
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile
from PIL import Image, UnidentifiedImageError
from sqlalchemy.orm import Session

from .. import models, schemas
from ..auth import get_current_admin
from ..database import get_db
from ..services.social_stats import cached_stats, refresh_stale_stats
from ..services.storage import store_image, storage_status

router = APIRouter(prefix="/api/media-kit", tags=["media-kit"])

UPLOAD_DIR = Path(__file__).resolve().parents[2] / "uploads" / "media-kit"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
MAX_IMAGE_BYTES = 8 * 1024 * 1024
IMAGE_FORMATS = {"JPEG": ".jpg", "PNG": ".png", "WEBP": ".webp", "GIF": ".gif"}
EXTRA_FIELDS = {
    "contact_email",
    "contact_phone",
    "profile_image_url",
    "cover_image_url",
    "social_links",
    "highlights",
    "audience_insights",
    "gallery",
    "content_pillars",
    "partner_reasons",
    "section_order",
    "hidden_sections",
}
LIST_FIELDS = {
    "rate_card",
    "testimonials",
    "past_collabs",
    "social_links",
    "highlights",
    "audience_insights",
    "gallery",
    "content_pillars",
    "partner_reasons",
    "section_order",
    "hidden_sections",
}
ITEM_LIST_FIELDS = {
    "rate_card",
    "testimonials",
    "past_collabs",
    "social_links",
    "highlights",
    "audience_insights",
    "gallery",
}
DEFAULT_SECTION_ORDER = [
    "pillars",
    "proof",
    "audience",
    "gallery",
    "case_studies",
    "services",
    "collaborations",
    "partner_reasons",
    "testimonials",
]


def _get_or_create(db: Session) -> models.MediaKitContent:
    content = db.query(models.MediaKitContent).first()
    if not content:
        content = models.MediaKitContent(id=1)
        db.add(content)
        db.commit()
        db.refresh(content)
    return content


def _serialize(content: models.MediaKitContent) -> dict:
    extras = content.extras or {}
    response = {
        "name": content.name,
        "tagline": content.tagline,
        "bio": content.bio,
        "location": content.location,
        "linkedin_followers": content.linkedin_followers,
        "linkedin_avg_impressions": content.linkedin_avg_impressions,
        "rate_card": content.rate_card or [],
        "testimonials": content.testimonials or [],
        "past_collabs": content.past_collabs or [],
        "instagram_handle": content.instagram_handle,
        "youtube_handle": content.youtube_handle,
        "linkedin_handle": content.linkedin_handle,
    }
    response.update({field: extras.get(field) for field in EXTRA_FIELDS})
    for field in LIST_FIELDS:
        response[field] = response.get(field) or []
    response["section_order"] = _valid_section_order(response["section_order"])
    return response


def _valid_section_order(value: list | None) -> list[str]:
    supplied = [item for item in (value or []) if item in DEFAULT_SECTION_ORDER]
    return list(dict.fromkeys(supplied + DEFAULT_SECTION_ORDER))


def _apply(content: models.MediaKitContent, updates: dict) -> None:
    extras = dict(content.extras or {})
    for field, value in updates.items():
        if field in EXTRA_FIELDS:
            extras[field] = value
        elif hasattr(content, field):
            setattr(content, field, value)
    content.extras = extras


def _public_only(payload: dict) -> dict:
    result = dict(payload)
    hidden_sections = set(result.get("hidden_sections") or [])
    for field in ITEM_LIST_FIELDS:
        result[field] = [
            item for item in (result.get(field) or [])
            if not isinstance(item, dict) or item.get("visible", True)
        ]
    section_fields = {
        "pillars": ("content_pillars",),
        "proof": ("highlights",),
        "audience": ("audience_insights", "social_links"),
        "gallery": ("gallery",),
        "services": ("rate_card",),
        "collaborations": ("past_collabs",),
        "partner_reasons": ("partner_reasons",),
        "testimonials": ("testimonials",),
    }
    for section in hidden_sections:
        for field in section_fields.get(section, ()):
            result[field] = []
    return result


def _publication(content: models.MediaKitContent) -> dict:
    return {
        "published_at": content.published_at.isoformat() if content.published_at else None,
        "published_by": content.published_by,
        "has_draft": content.draft_content is not None,
    }


@router.get("/")
def get_media_kit(background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """Public endpoint powering the shareable media-kit page."""
    content = _get_or_create(db)
    response = _public_only(_serialize(content))
    live_stats = cached_stats(db)
    db.commit()
    response["live_social_stats"] = live_stats
    for social in response["social_links"]:
        platform = str(social.get("platform") or "").casefold()
        live = live_stats.get(platform)
        if not live or live["status"] != "synced":
            continue
        values = live["data"]
        social["follower_count"] = values.get("followers", social.get("follower_count"))
        if platform == "youtube" and values.get("total_views") is not None:
            social["secondary_stat"] = f"{values['total_views']:,} total channel views"
        elif platform == "instagram" and values.get("media_count") is not None:
            social["secondary_stat"] = f"{values['media_count']:,} published posts"
        social["live"] = True
        social["last_synced_at"] = live["last_synced_at"]
    background_tasks.add_task(refresh_stale_stats)
    return response


@router.get("/draft")
def get_media_kit_draft(
    db: Session = Depends(get_db),
    admin=Depends(get_current_admin),
):
    """Return the manager working copy without exposing it publicly."""
    content = _get_or_create(db)
    response = dict(content.draft_content or _serialize(content))
    response["section_order"] = _valid_section_order(response.get("section_order"))
    response["_publication"] = _publication(content)
    return response


@router.put("/draft")
def save_media_kit_draft(
    payload: schemas.MediaKitUpdate,
    db: Session = Depends(get_db),
    admin=Depends(get_current_admin),
):
    """Save a complete draft without changing the public media kit."""
    content = _get_or_create(db)
    draft = payload.model_dump(exclude_unset=True, mode="json")
    draft["section_order"] = _valid_section_order(draft.get("section_order"))
    content.draft_content = draft
    db.commit()
    return {
        "message": "Draft saved",
        "publication": _publication(content),
    }


@router.post("/publish")
def publish_media_kit(
    db: Session = Depends(get_db),
    admin=Depends(get_current_admin),
):
    """Promote the saved draft to the public media kit."""
    content = _get_or_create(db)
    if content.draft_content is None:
        raise HTTPException(409, "Save a draft before publishing")
    draft = dict(content.draft_content)
    draft["section_order"] = _valid_section_order(draft.get("section_order"))
    _apply(content, draft)
    content.published_at = datetime.now(timezone.utc)
    content.published_by = str(admin)
    db.commit()
    db.refresh(content)
    return {
        "message": "Media kit published",
        "publication": _publication(content),
    }


@router.put("/")
def update_media_kit(
    payload: schemas.MediaKitUpdate,
    db: Session = Depends(get_db),
    admin=Depends(get_current_admin),
):
    """Backward-compatible immediate update used by older clients."""
    content = _get_or_create(db)
    updates = payload.model_dump(exclude_unset=True, mode="json")
    updates["section_order"] = _valid_section_order(updates.get("section_order"))
    _apply(content, updates)
    content.draft_content = _serialize(content)
    content.published_at = datetime.now(timezone.utc)
    content.published_by = str(admin)
    db.commit()
    db.refresh(content)
    return {"message": "Media kit updated"}


@router.post("/upload")
async def upload_media_image(
    file: UploadFile = File(...),
    admin=Depends(get_current_admin),
):
    """Upload and verify an image used by the public media kit."""
    contents = await file.read(MAX_IMAGE_BYTES + 1)
    if len(contents) > MAX_IMAGE_BYTES:
        raise HTTPException(413, "Image must be 8 MB or smaller")

    try:
        with Image.open(BytesIO(contents)) as image:
            image.verify()
            image_format = image.format
    except (UnidentifiedImageError, OSError):
        raise HTTPException(400, "Please upload a valid JPG, PNG, WebP, or GIF image")

    extension = IMAGE_FORMATS.get(image_format)
    if not extension:
        raise HTTPException(400, "Unsupported image format")

    try:
        result = store_image(
            contents,
            original_filename=file.filename or f"media-kit{extension}",
            content_type=file.content_type or f"image/{extension.lstrip('.')}",
            local_directory=UPLOAD_DIR,
            local_url_prefix="/api/uploads/media-kit",
            local_extension=extension,
        )
    except RuntimeError as exc:
        raise HTTPException(503, str(exc)) from exc
    return {
        "url": result.url,
        "storage_backend": result.backend,
        "public_id": result.public_id,
    }


@router.get("/storage-status")
def get_storage_status(admin=Depends(get_current_admin)):
    return storage_status()
