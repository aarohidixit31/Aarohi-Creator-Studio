import os
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from .. import models
from .instagram_oauth import access_credentials, connection_status, graph_get, graph_get_url


INSTAGRAM_IMPORT_LIMIT = max(1, min(500, int(os.getenv("INSTAGRAM_CONTENT_IMPORT_LIMIT", "200"))))
MEDIA_FIELDS = "id,caption,media_type,media_product_type,permalink,thumbnail_url,media_url,timestamp,like_count,comments_count"
INSIGHT_METRICS = (
    "views", "plays", "reach", "likes", "comments", "saved", "shares",
    "total_interactions", "follows", "profile_visits", "ig_reels_avg_watch_time",
)


def _published_at(value: str | None):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _existing_maps(db: Session):
    items = db.query(models.ContentItem).filter(models.ContentItem.platform == "Instagram").all()
    by_external_id = {
        str((item.metrics or {}).get("external_id")): item
        for item in items
        if (item.metrics or {}).get("external_id")
    }
    by_url = {item.content_url.rstrip("/"): item for item in items if item.content_url}
    return items, by_external_id, by_url


def fetch_instagram_media(db: Session) -> list[dict]:
    _, account_id = access_credentials(db)
    payload = graph_get(db, f"{account_id}/media", {"fields": MEDIA_FIELDS, "limit": min(100, INSTAGRAM_IMPORT_LIMIT)})
    result = list(payload.get("data") or [])
    next_url = ((payload.get("paging") or {}).get("next"))
    while next_url and len(result) < INSTAGRAM_IMPORT_LIMIT:
        payload = graph_get_url(db, next_url)
        result.extend(payload.get("data") or [])
        next_url = ((payload.get("paging") or {}).get("next"))
    return result[:INSTAGRAM_IMPORT_LIMIT]


def _thumbnail(media: dict) -> str | None:
    return media.get("thumbnail_url") or media.get("media_url")


def _title(media: dict) -> str:
    caption = (media.get("caption") or "").strip()
    if caption:
        first_line = caption.splitlines()[0].strip()
        return first_line[:117] + "..." if len(first_line) > 120 else first_line
    product = (media.get("media_product_type") or media.get("media_type") or "Post").replace("_", " ").title()
    published = _published_at(media.get("timestamp"))
    return f"Instagram {product}" + (f" · {published.strftime('%d %b %Y')}" if published else "")


def _insight_value(payload: dict):
    rows = payload.get("data") or []
    if not rows:
        return None
    row = rows[0]
    if isinstance(row.get("total_value"), dict):
        return row["total_value"].get("value")
    values = row.get("values") or []
    return values[-1].get("value") if values else None


def media_insights(db: Session, media_id: str) -> dict:
    result = {}
    for metric in INSIGHT_METRICS:
        try:
            value = _insight_value(graph_get(db, f"{media_id}/insights", {"metric": metric}))
            if value is not None:
                result[metric] = value
        except RuntimeError:
            # Instagram exposes different metrics for Reels, posts and carousels.
            # Unsupported metrics should not prevent the remaining insights syncing.
            continue
    return result


def instagram_catalog(db: Session) -> dict:
    oauth = connection_status(db)
    if not oauth["connected"]:
        return {"items": [], "oauth": oauth, "import_limit": INSTAGRAM_IMPORT_LIMIT}
    media = fetch_instagram_media(db)
    _, by_external_id, by_url = _existing_maps(db)
    items = []
    for entry in media:
        media_id = str(entry.get("id") or "")
        permalink = entry.get("permalink")
        if not media_id or not permalink:
            continue
        existing = by_external_id.get(media_id) or by_url.get(permalink.rstrip("/"))
        items.append({
            "media_id": media_id,
            "title": _title(entry),
            "content_url": permalink,
            "thumbnail_url": _thumbnail(entry),
            "published_at": _published_at(entry.get("timestamp")),
            "media_type": entry.get("media_type"),
            "media_product_type": entry.get("media_product_type"),
            "views": 0,
            "likes": int(entry.get("like_count") or 0),
            "comments": int(entry.get("comments_count") or 0),
            "already_imported": bool(existing),
            "content_id": existing.id if existing else None,
        })
    return {"items": items, "oauth": oauth, "import_limit": INSTAGRAM_IMPORT_LIMIT}


def sync_instagram_content(db: Session, selected_ids: list[str]) -> dict:
    selected_ids = list(dict.fromkeys(value.strip() for value in selected_ids if value.strip()))
    if not selected_ids:
        raise RuntimeError("Select at least one Instagram post or Reel")
    if len(selected_ids) > INSTAGRAM_IMPORT_LIMIT:
        raise RuntimeError(f"Select no more than {INSTAGRAM_IMPORT_LIMIT} Instagram items at a time")
    selected = set(selected_ids)
    media = [item for item in fetch_instagram_media(db) if str(item.get("id")) in selected]
    _, by_external_id, by_url = _existing_maps(db)
    now = datetime.now(timezone.utc)
    imported = updated = 0
    imported_ids = []

    for entry in media:
        media_id = str(entry["id"])
        permalink = entry.get("permalink") or f"https://instagram.com/p/{media_id}"
        item = by_external_id.get(media_id) or by_url.get(permalink.rstrip("/"))
        old_metrics = dict(item.metrics or {}) if item else {}
        insights = media_insights(db, media_id)
        average_watch_ms = insights.get("ig_reels_avg_watch_time")
        metrics = {
            **old_metrics,
            "views": int(insights.get("views") or insights.get("plays") or old_metrics.get("views") or 0),
            "reach": int(insights["reach"]) if insights.get("reach") is not None else old_metrics.get("reach"),
            "likes": int(insights.get("likes") or entry.get("like_count") or 0),
            "comments": int(insights.get("comments") or entry.get("comments_count") or 0),
            "saves": int(insights["saved"]) if insights.get("saved") is not None else old_metrics.get("saves"),
            "shares": int(insights["shares"]) if insights.get("shares") is not None else old_metrics.get("shares"),
            "follows": int(insights["follows"]) if insights.get("follows") is not None else old_metrics.get("follows"),
            "profile_visits": int(insights["profile_visits"]) if insights.get("profile_visits") is not None else old_metrics.get("profile_visits"),
            "average_watch_time_seconds": round(float(average_watch_ms) / 1000, 2) if average_watch_ms is not None else old_metrics.get("average_watch_time_seconds"),
            "total_interactions": int(insights["total_interactions"]) if insights.get("total_interactions") is not None else old_metrics.get("total_interactions"),
            "verification_method": "api",
            "measured_at": now.isoformat(),
            "external_id": media_id,
            "sync_source": "instagram_graph_api",
            "media_type": entry.get("media_type"),
            "media_product_type": entry.get("media_product_type"),
            "review_status": old_metrics.get("review_status") or "pending",
        }
        values = {
            "title": _title(entry),
            "content_url": permalink,
            "thumbnail_url": _thumbnail(entry),
            "published_at": _published_at(entry.get("timestamp")),
            "metrics": metrics,
        }
        if item:
            for field, value in values.items():
                setattr(item, field, value)
            updated += 1
        else:
            item = models.ContentItem(platform="Instagram", featured=False, **values)
            db.add(item)
            db.flush()
            imported += 1
            imported_ids.append(item.id)

    db.commit()
    return {
        "platform": "instagram",
        "discovered": len(selected_ids),
        "imported": imported,
        "updated": updated,
        "skipped": max(0, len(selected_ids) - len(media)),
        "pending_review": sum(
            (item.metrics or {}).get("review_status") == "pending"
            for item in db.query(models.ContentItem).filter(models.ContentItem.platform == "Instagram").all()
        ),
        "imported_ids": imported_ids,
        "synced_at": now,
        "analytics_connected": True,
        "analytics_error": None,
    }


def refresh_imported_instagram_content(db: Session) -> dict:
    items = db.query(models.ContentItem).filter(models.ContentItem.platform == "Instagram").all()
    media_ids = [(item.metrics or {}).get("external_id") for item in items]
    return sync_instagram_content(db, [str(media_id) for media_id in media_ids if media_id])
