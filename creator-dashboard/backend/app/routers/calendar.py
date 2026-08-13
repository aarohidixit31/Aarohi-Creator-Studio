from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload

from .. import models, schemas
from ..auth import get_current_admin
from ..database import get_db


router = APIRouter(prefix="/api/calendar", tags=["calendar"])


def _utc(value: datetime | str | None) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


@router.get("/", response_model=schemas.CalendarOut)
def manager_calendar(
    start: datetime = Query(...),
    end: datetime = Query(...),
    db: Session = Depends(get_db),
    admin=Depends(get_current_admin),
):
    """Return manager-facing deadlines and scheduled activity for a date window."""
    window_start = _utc(start)
    window_end = _utc(end)
    if not window_start or not window_end or window_end <= window_start:
        raise HTTPException(400, "End must be after start")
    if (window_end - window_start).days > 93:
        raise HTTPException(400, "Calendar range cannot exceed 93 days")

    events = []
    collabs = (
        db.query(models.Collab)
        .options(joinedload(models.Collab.brand))
        .filter(models.Collab.archived_at.is_(None))
        .all()
    )
    for collab in collabs:
        brand_name = collab.brand.name if collab.brand else f"Brand #{collab.brand_id}"
        deadline = _utc(collab.deadline)
        if deadline and window_start <= deadline < window_end:
            events.append({
                "key": f"deadline-{collab.id}",
                "type": "deadline",
                "title": "Campaign deadline",
                "starts_at": deadline,
                "brand_name": brand_name,
                "detail": collab.campaign_type or collab.deliverables,
                "status": collab.status,
                "href": f"/admin/collabs/{collab.id}",
            })

        follow_up = _utc((collab.details or {}).get("follow_up_at"))
        if follow_up and window_start <= follow_up < window_end:
            events.append({
                "key": f"follow-up-{collab.id}",
                "type": "follow_up",
                "title": "Brand follow-up",
                "starts_at": follow_up,
                "brand_name": brand_name,
                "detail": (collab.details or {}).get("next_action") or collab.campaign_type,
                "status": collab.status,
                "href": f"/admin/collabs/{collab.id}",
            })

    invoices = (
        db.query(models.Invoice)
        .options(joinedload(models.Invoice.brand))
        .filter(models.Invoice.due_date.is_not(None))
        .all()
    )
    for invoice in invoices:
        due_date = _utc(invoice.due_date)
        if due_date and window_start <= due_date < window_end:
            events.append({
                "key": f"invoice-{invoice.id}",
                "type": "invoice",
                "title": f"{invoice.invoice_number} due",
                "starts_at": due_date,
                "brand_name": invoice.brand.name if invoice.brand else f"Brand #{invoice.brand_id}",
                "detail": invoice.payment_terms,
                "status": invoice.status,
                "amount": invoice.total or 0,
                "href": "/admin/invoices",
            })

    content_items = (
        db.query(models.ContentItem)
        .options(joinedload(models.ContentItem.brand))
        .filter(models.ContentItem.published_at.is_not(None))
        .all()
    )
    for item in content_items:
        published_at = _utc(item.published_at)
        if published_at and window_start <= published_at < window_end:
            events.append({
                "key": f"content-{item.id}",
                "type": "content",
                "title": item.title,
                "starts_at": published_at,
                "brand_name": item.brand.name if item.brand else None,
                "detail": item.platform,
                "status": "published",
                "href": "/admin/content",
            })

    events.sort(key=lambda event: (event["starts_at"], event["type"], event["title"]))
    return {"start": window_start, "end": window_end, "events": events}
