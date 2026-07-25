from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas
from ..auth import get_current_admin
from ..database import get_db
from ..services.social_stats import PLATFORMS, cached_stats, refresh_platform

router = APIRouter(prefix="/api/social-stats", tags=["social-stats"])


@router.get("/history", response_model=list[schemas.SocialStatSnapshotOut])
def social_stat_history(
    platform: str = "all",
    days: int = 365,
    db: Session = Depends(get_db),
    admin=Depends(get_current_admin),
):
    if platform != "all" and platform not in PLATFORMS:
        raise HTTPException(400, f"Platform must be all, {', '.join(PLATFORMS)}")
    days = min(730, max(7, days))
    query = db.query(models.SocialStatSnapshot).filter(
        models.SocialStatSnapshot.captured_at >= datetime.now(timezone.utc) - timedelta(days=days)
    )
    if platform != "all":
        query = query.filter(models.SocialStatSnapshot.platform == platform)
    return query.order_by(models.SocialStatSnapshot.captured_at.asc()).all()


@router.get("/", response_model=list[schemas.SocialStatOut])
def list_social_stats(db: Session = Depends(get_db), admin=Depends(get_current_admin)):
    stats = cached_stats(db)
    db.commit()
    return [stats[platform] for platform in PLATFORMS]


@router.post("/refresh", response_model=list[schemas.SocialStatOut])
def refresh_social_stats(
    platform: str = "all",
    db: Session = Depends(get_db),
    admin=Depends(get_current_admin),
):
    selected = PLATFORMS if platform == "all" else (platform.lower(),)
    if any(item not in PLATFORMS for item in selected):
        raise HTTPException(400, f"Platform must be all, {', '.join(PLATFORMS)}")
    return [refresh_platform(db, item, force=True) for item in selected]
