import os
import re
from datetime import datetime, timezone
from urllib.parse import parse_qs, urlencode, urlparse

from sqlalchemy.orm import Session

from .. import models
from .social_stats import _get_json
from .youtube_oauth import connection_status, video_analytics


YOUTUBE_API_ROOT = "https://www.googleapis.com/youtube/v3"
YOUTUBE_IMPORT_LIMIT = max(1, min(500, int(os.getenv("YOUTUBE_CONTENT_IMPORT_LIMIT", "200"))))


def _youtube_settings() -> tuple[str, str, str]:
    api_key = os.getenv("YOUTUBE_API_KEY", "").strip()
    channel_id = os.getenv("YOUTUBE_CHANNEL_ID", "").strip()
    handle = os.getenv("YOUTUBE_HANDLE", "").strip()
    if not api_key or not (channel_id or handle):
        raise RuntimeError("Add YOUTUBE_API_KEY and YOUTUBE_CHANNEL_ID or YOUTUBE_HANDLE")
    return api_key, channel_id, handle


def _api(path: str, params: dict) -> dict:
    return _get_json(f"{YOUTUBE_API_ROOT}/{path}?{urlencode(params)}")


def _uploads_playlist(api_key: str, channel_id: str, handle: str) -> str:
    params = {"part": "contentDetails", "key": api_key}
    params["id" if channel_id else "forHandle"] = channel_id or handle
    payload = _api("channels", params)
    items = payload.get("items") or []
    if not items:
        raise RuntimeError("YouTube channel was not found")
    playlist_id = ((items[0].get("contentDetails") or {}).get("relatedPlaylists") or {}).get("uploads")
    if not playlist_id:
        raise RuntimeError("YouTube uploads playlist was not available")
    return playlist_id


def _video_ids(api_key: str, playlist_id: str) -> list[str]:
    result = []
    page_token = None
    while len(result) < YOUTUBE_IMPORT_LIMIT:
        params = {
            "part": "contentDetails",
            "playlistId": playlist_id,
            "maxResults": min(50, YOUTUBE_IMPORT_LIMIT - len(result)),
            "key": api_key,
        }
        if page_token:
            params["pageToken"] = page_token
        payload = _api("playlistItems", params)
        for item in payload.get("items") or []:
            video_id = (item.get("contentDetails") or {}).get("videoId")
            if video_id:
                result.append(video_id)
        page_token = payload.get("nextPageToken")
        if not page_token or not payload.get("items"):
            break
    return result


def _duration_seconds(value: str | None) -> int | None:
    if not value:
        return None
    match = re.fullmatch(r"P(?:(\d+)D)?T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", value)
    if not match:
        return None
    days, hours, minutes, seconds = (int(part or 0) for part in match.groups())
    return days * 86400 + hours * 3600 + minutes * 60 + seconds


def _thumbnail(snippet: dict) -> str | None:
    thumbnails = snippet.get("thumbnails") or {}
    for quality in ("maxres", "standard", "high", "medium", "default"):
        if (thumbnails.get(quality) or {}).get("url"):
            return thumbnails[quality]["url"]
    return None


def _videos(api_key: str, video_ids: list[str]) -> list[dict]:
    result = []
    for start in range(0, len(video_ids), 50):
        payload = _api("videos", {
            "part": "snippet,statistics,contentDetails,status",
            "id": ",".join(video_ids[start:start + 50]),
            "key": api_key,
        })
        result.extend(payload.get("items") or [])
    return result


def fetch_youtube_content(selected_ids: list[str] | None = None) -> list[dict]:
    api_key, channel_id, handle = _youtube_settings()
    playlist_id = _uploads_playlist(api_key, channel_id, handle)
    video_ids = _video_ids(api_key, playlist_id)
    if selected_ids is not None:
        requested = set(selected_ids)
        video_ids = [video_id for video_id in video_ids if video_id in requested]
    return _videos(api_key, video_ids)


def _published_at(value: str | None):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _youtube_id(value: str | None) -> str | None:
    if not value:
        return None
    try:
        parsed = urlparse(value)
        hostname = parsed.hostname.casefold() if parsed.hostname else ""
        if hostname in {"youtu.be", "www.youtu.be"}:
            return parsed.path.strip("/").split("/")[0] or None
        if hostname.endswith("youtube.com"):
            if parsed.path == "/watch":
                return (parse_qs(parsed.query).get("v") or [None])[0]
            parts = parsed.path.strip("/").split("/")
            if len(parts) >= 2 and parts[0] in {"shorts", "embed", "live"}:
                return parts[1]
    except (AttributeError, ValueError):
        pass
    return None


def _pending_review(db: Session) -> int:
    return sum(
        (item.metrics or {}).get("review_status") == "pending"
        for item in db.query(models.ContentItem).filter(models.ContentItem.platform == "YouTube").all()
    )


def _existing_maps(db: Session):
    existing = db.query(models.ContentItem).filter(models.ContentItem.platform == "YouTube").all()
    by_external_id = {
        str((item.metrics or {}).get("external_id")): item
        for item in existing
        if (item.metrics or {}).get("external_id")
    }
    by_url_id = {_youtube_id(item.content_url): item for item in existing if _youtube_id(item.content_url)}
    return existing, by_external_id, by_url_id


def youtube_catalog(db: Session) -> dict:
    videos = fetch_youtube_content()
    _, by_external_id, by_url_id = _existing_maps(db)
    candidates = []
    for video in videos:
        video_id = video.get("id")
        snippet = video.get("snippet") or {}
        statistics = video.get("statistics") or {}
        status = video.get("status") or {}
        if not video_id or status.get("privacyStatus") not in (None, "public"):
            continue
        existing = by_external_id.get(video_id) or by_url_id.get(video_id)
        candidates.append({
            "video_id": video_id,
            "title": (snippet.get("title") or f"YouTube video {video_id}").strip(),
            "content_url": f"https://www.youtube.com/watch?v={video_id}",
            "thumbnail_url": _thumbnail(snippet),
            "published_at": _published_at(snippet.get("publishedAt")),
            "duration_seconds": _duration_seconds((video.get("contentDetails") or {}).get("duration")),
            "views": int(statistics.get("viewCount") or 0),
            "likes": int(statistics.get("likeCount") or 0),
            "comments": int(statistics.get("commentCount") or 0),
            "already_imported": bool(existing),
            "content_id": existing.id if existing else None,
        })
    return {
        "items": candidates,
        "oauth": connection_status(db),
        "import_limit": YOUTUBE_IMPORT_LIMIT,
    }


def sync_youtube_content(db: Session, selected_ids: list[str]) -> dict:
    selected_ids = list(dict.fromkeys(value.strip() for value in selected_ids if value.strip()))
    if not selected_ids:
        raise RuntimeError("Select at least one YouTube video")
    if len(selected_ids) > YOUTUBE_IMPORT_LIMIT:
        raise RuntimeError(f"Select no more than {YOUTUBE_IMPORT_LIMIT} videos at a time")
    videos = fetch_youtube_content(selected_ids)
    now = datetime.now(timezone.utc)
    oauth = connection_status(db)
    analytics = {}
    analytics_error = None
    if oauth["connected"]:
        try:
            analytics = video_analytics(db, [video.get("id") for video in videos if video.get("id")])
        except RuntimeError as exc:
            analytics_error = str(exc)
    _, by_external_id, by_url_id = _existing_maps(db)
    imported = updated = 0
    skipped = max(0, len(selected_ids) - len(videos))
    imported_ids = []

    for video in videos:
        video_id = video.get("id")
        snippet = video.get("snippet") or {}
        statistics = video.get("statistics") or {}
        status = video.get("status") or {}
        if not video_id or status.get("privacyStatus") not in (None, "public"):
            skipped += 1
            continue
        url = f"https://www.youtube.com/watch?v={video_id}"
        item = by_external_id.get(video_id) or by_url_id.get(video_id)
        old_metrics = dict(item.metrics or {}) if item else {}
        private_metrics = analytics.get(video_id) or {}
        metrics = {
            **old_metrics,
            "views": int(statistics.get("viewCount") or 0),
            "likes": int(statistics.get("likeCount") or 0),
            "comments": int(statistics.get("commentCount") or 0),
            "shares": int(private_metrics.get("shares") or old_metrics.get("shares") or 0) if private_metrics else old_metrics.get("shares"),
            "average_watch_time_seconds": float(private_metrics.get("averageViewDuration")) if private_metrics.get("averageViewDuration") is not None else old_metrics.get("average_watch_time_seconds"),
            "average_view_percentage": float(private_metrics.get("averageViewPercentage")) if private_metrics.get("averageViewPercentage") is not None else old_metrics.get("average_view_percentage"),
            "estimated_minutes_watched": float(private_metrics.get("estimatedMinutesWatched")) if private_metrics.get("estimatedMinutesWatched") is not None else old_metrics.get("estimated_minutes_watched"),
            "follows": int(private_metrics.get("subscribersGained")) if private_metrics.get("subscribersGained") is not None else old_metrics.get("follows"),
            "verification_method": "api",
            "measured_at": now.isoformat(),
            "external_id": video_id,
            "sync_source": "youtube_analytics_api" if private_metrics else "youtube_data_api",
            "duration_seconds": _duration_seconds((video.get("contentDetails") or {}).get("duration")),
            "review_status": old_metrics.get("review_status") or "pending",
        }
        values = {
            "title": (snippet.get("title") or f"YouTube video {video_id}").strip(),
            "content_url": url,
            "thumbnail_url": _thumbnail(snippet),
            "published_at": _published_at(snippet.get("publishedAt")),
            "metrics": metrics,
        }
        if item:
            for field, value in values.items():
                setattr(item, field, value)
            updated += 1
        else:
            item = models.ContentItem(platform="YouTube", featured=False, **values)
            db.add(item)
            db.flush()
            imported += 1
            imported_ids.append(item.id)

    db.commit()
    return {
        "platform": "youtube",
        "discovered": len(selected_ids),
        "imported": imported,
        "updated": updated,
        "skipped": skipped,
        "pending_review": _pending_review(db),
        "imported_ids": imported_ids,
        "synced_at": now.isoformat(),
        "analytics_connected": oauth["connected"],
        "analytics_error": analytics_error,
    }


def refresh_imported_youtube_content(db: Session) -> dict:
    items = db.query(models.ContentItem).filter(models.ContentItem.platform == "YouTube").all()
    video_ids = [
        (item.metrics or {}).get("external_id") or _youtube_id(item.content_url)
        for item in items
    ]
    return sync_youtube_content(db, [video_id for video_id in video_ids if video_id])
