from io import BytesIO
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from PIL import Image, UnidentifiedImageError
from sqlalchemy.orm import Session

from .. import models, schemas
from ..auth import get_current_admin
from ..database import get_db

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
}


def _get_or_create(db: Session) -> models.MediaKitContent:
    content = db.query(models.MediaKitContent).first()
    if not content:
        content = models.MediaKitContent(id=1)
        db.add(content)
        db.commit()
        db.refresh(content)
    return content


@router.get("/")
def get_media_kit(db: Session = Depends(get_db)):
    """Public endpoint powering the shareable media-kit page."""
    content = _get_or_create(db)
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
    response["social_links"] = response["social_links"] or []
    response["highlights"] = response["highlights"] or []
    response["audience_insights"] = response["audience_insights"] or []
    response["gallery"] = response["gallery"] or []
    response["content_pillars"] = response["content_pillars"] or []
    response["partner_reasons"] = response["partner_reasons"] or []
    return response


@router.put("/")
def update_media_kit(
    payload: schemas.MediaKitUpdate,
    db: Session = Depends(get_db),
    admin=Depends(get_current_admin),
):
    """Admin-only endpoint for the complete media-kit editor."""
    content = _get_or_create(db)
    updates = payload.model_dump(exclude_unset=True)
    extras = dict(content.extras or {})

    for field, value in updates.items():
        if field in EXTRA_FIELDS:
            if isinstance(value, list):
                value = [
                    item.model_dump() if hasattr(item, "model_dump") else item
                    for item in value
                ]
            extras[field] = value
            continue

        if field in ("rate_card", "testimonials", "past_collabs") and value is not None:
            value = [
                item if isinstance(item, dict) else item.model_dump()
                for item in value
            ]
        setattr(content, field, value)

    content.extras = extras
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

    filename = f"{uuid4().hex}{extension}"
    (UPLOAD_DIR / filename).write_bytes(contents)
    return {"url": f"/api/uploads/media-kit/{filename}"}
