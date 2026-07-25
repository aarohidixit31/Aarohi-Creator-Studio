import json
import os
from datetime import datetime, timedelta, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from sqlalchemy.orm import Session

from .. import models
from ..database import SessionLocal

PLATFORMS = ("instagram", "youtube")
CACHE_HOURS = max(1, int(os.getenv("SOCIAL_STATS_CACHE_HOURS", "6")))


def platform_is_configured(platform: str) -> bool:
    if platform == "youtube":
        return bool(
            os.getenv("YOUTUBE_API_KEY")
            and (os.getenv("YOUTUBE_CHANNEL_ID") or os.getenv("YOUTUBE_HANDLE"))
        )
    if platform == "instagram":
        return bool(os.getenv("META_ACCESS_TOKEN") and os.getenv("INSTAGRAM_ACCOUNT_ID"))
    return False


def _cache(db: Session, platform: str) -> models.SocialStatCache:
    cache = (
        db.query(models.SocialStatCache)
        .filter(models.SocialStatCache.platform == platform)
        .first()
    )
    if not cache:
        cache = models.SocialStatCache(platform=platform, status="disconnected", data={})
        db.add(cache)
        db.flush()
    return cache


def cache_payload(db: Session, platform: str) -> dict:
    cache = _cache(db, platform)
    return {
        "platform": platform,
        "configured": platform_is_configured(platform),
        "status": cache.status,
        "data": cache.data or {},
        "error": cache.error,
        "last_attempted_at": cache.last_attempted_at,
        "last_synced_at": cache.last_synced_at,
        "cache_hours": CACHE_HOURS,
    }


def cached_stats(db: Session) -> dict:
    return {platform: cache_payload(db, platform) for platform in PLATFORMS}


def _is_fresh(cache: models.SocialStatCache, now: datetime) -> bool:
    if not cache.last_synced_at:
        return False
    synced = cache.last_synced_at
    if synced.tzinfo is None:
        synced = synced.replace(tzinfo=timezone.utc)
    return synced >= now - timedelta(hours=CACHE_HOURS)


def _attempted_recently(cache: models.SocialStatCache, now: datetime) -> bool:
    if not cache.last_attempted_at:
        return False
    attempted = cache.last_attempted_at
    if attempted.tzinfo is None:
        attempted = attempted.replace(tzinfo=timezone.utc)
    return attempted >= now - timedelta(minutes=30)


def _get_json(url: str) -> dict:
    request = Request(url, headers={"User-Agent": "AarohiCreatorDashboard/1.0"})
    try:
        with urlopen(request, timeout=12) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        detail = ""
        try:
            body = json.loads(exc.read().decode("utf-8"))
            detail = body.get("error", {}).get("message") or body.get("error", {}).get("errors", [{}])[0].get("message", "")
        except (ValueError, AttributeError, IndexError):
            pass
        raise RuntimeError(detail or f"API returned HTTP {exc.code}") from exc
    except (URLError, TimeoutError) as exc:
        raise RuntimeError("Could not reach the platform API") from exc


def _youtube_stats() -> dict:
    api_key = os.getenv("YOUTUBE_API_KEY", "").strip()
    channel_id = os.getenv("YOUTUBE_CHANNEL_ID", "").strip()
    handle = os.getenv("YOUTUBE_HANDLE", "").strip()
    if not api_key or not (channel_id or handle):
        raise RuntimeError("Add YOUTUBE_API_KEY and YOUTUBE_CHANNEL_ID or YOUTUBE_HANDLE")
    params = {"part": "snippet,statistics", "key": api_key}
    params["id" if channel_id else "forHandle"] = channel_id or handle
    payload = _get_json(f"https://www.googleapis.com/youtube/v3/channels?{urlencode(params)}")
    if not payload.get("items"):
        raise RuntimeError("YouTube channel was not found")
    channel = payload["items"][0]
    statistics = channel.get("statistics") or {}
    return {
        "account_id": channel.get("id"),
        "title": (channel.get("snippet") or {}).get("title"),
        "followers": int(statistics.get("subscriberCount") or 0),
        "total_views": int(statistics.get("viewCount") or 0),
        "media_count": int(statistics.get("videoCount") or 0),
        "followers_hidden": bool(statistics.get("hiddenSubscriberCount")),
    }


def _instagram_stats() -> dict:
    token = os.getenv("META_ACCESS_TOKEN", "").strip()
    account_id = os.getenv("INSTAGRAM_ACCOUNT_ID", "").strip()
    version = os.getenv("META_GRAPH_VERSION", "v23.0").strip()
    base_url = os.getenv("INSTAGRAM_GRAPH_BASE_URL", "https://graph.facebook.com").rstrip("/")
    if not token or not account_id:
        raise RuntimeError("Add META_ACCESS_TOKEN and INSTAGRAM_ACCOUNT_ID")
    params = {
        "fields": "id,username,followers_count,media_count",
        "access_token": token,
    }
    payload = _get_json(f"{base_url}/{version}/{account_id}?{urlencode(params)}")
    return {
        "account_id": payload.get("id") or account_id,
        "username": payload.get("username"),
        "followers": int(payload.get("followers_count") or 0),
        "media_count": int(payload.get("media_count") or 0),
    }


def refresh_platform(db: Session, platform: str, force: bool = False) -> dict:
    if platform not in PLATFORMS:
        raise ValueError("Unsupported platform")
    cache = _cache(db, platform)
    now = datetime.now(timezone.utc)
    if not force and _is_fresh(cache, now):
        return cache_payload(db, platform)
    if not force and cache.status in ("error", "disconnected") and _attempted_recently(cache, now):
        return cache_payload(db, platform)

    cache.last_attempted_at = now
    if not platform_is_configured(platform):
        cache.status = "disconnected"
        cache.error = "API credentials are not configured"
        db.commit()
        return cache_payload(db, platform)

    try:
        cache.data = _youtube_stats() if platform == "youtube" else _instagram_stats()
        cache.status = "synced"
        cache.error = None
        cache.last_synced_at = now
        latest_snapshot = (
            db.query(models.SocialStatSnapshot)
            .filter(models.SocialStatSnapshot.platform == platform)
            .order_by(models.SocialStatSnapshot.captured_at.desc())
            .first()
        )
        latest_date = None
        if latest_snapshot and latest_snapshot.captured_at:
            captured = latest_snapshot.captured_at
            if captured.tzinfo is None:
                captured = captured.replace(tzinfo=timezone.utc)
            latest_date = captured.date()
        if latest_date != now.date():
            db.add(models.SocialStatSnapshot(
                platform=platform,
                followers=int(cache.data.get("followers") or 0),
                total_views=cache.data.get("total_views"),
                media_count=cache.data.get("media_count"),
                captured_at=now,
            ))
    except RuntimeError as exc:
        cache.status = "error"
        cache.error = str(exc)[:1000]
    db.commit()
    return cache_payload(db, platform)


def refresh_stale_stats() -> None:
    db = SessionLocal()
    try:
        for platform in PLATFORMS:
            refresh_platform(db, platform, force=False)
    finally:
        db.close()
