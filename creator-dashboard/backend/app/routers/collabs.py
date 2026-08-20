from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload, selectinload

from .. import models, schemas
from ..auth import get_current_admin
from ..database import get_db
from ..services.email import email_is_configured, send_inquiry_notifications
from ..services.storage import store_document

router = APIRouter(prefix="/api/collabs", tags=["collabs"])

VALID_STATUSES = [
    "new",
    "in_discussion",
    "negotiating",
    "confirmed",
    "agreement_invoice",
    "script_approved",
    "shoot_done",
    "draft_submitted",
    "content_posted",
    "payment_received",
    "closed",
]
VALID_PRIORITIES = {"low", "normal", "high", "urgent"}
VALID_ASSIGNEES = {"unassigned", "aarohi", "manager"}
VALID_WAITING_ON = {"none", "brand", "aarohi", "manager"}
RESOURCE_KINDS = {
    "Brief", "Script", "Contract", "Draft", "Reference", "Brand assets",
    "Drive folder", "Live content", "Other",
}
RESOURCE_UPLOAD_DIR = Path(__file__).resolve().parents[2] / "uploads" / "collab-resources"
MAX_RESOURCE_BYTES = 15 * 1024 * 1024
ALLOWED_RESOURCE_TYPES = {
    "application/pdf": ".pdf",
    "application/msword": ".doc",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
    "application/vnd.ms-excel": ".xls",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": ".xlsx",
    "application/vnd.ms-powerpoint": ".ppt",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation": ".pptx",
    "application/zip": ".zip",
    "text/plain": ".txt",
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}


def _activity(
    action: str,
    detail: str | None = None,
    from_status: str | None = None,
    to_status: str | None = None,
) -> dict:
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "action": action,
        "detail": detail,
        "from_status": from_status,
        "to_status": to_status,
    }


def _detail_payload(collab: models.Collab) -> dict:
    details = collab.details or {}
    activity_log = details.get("activity_log") or []
    stage_entered_at = collab.created_at
    for event in reversed(activity_log):
        if event.get("action") == "status_changed" and event.get("timestamp"):
            stage_entered_at = event["timestamp"]
            break
    resources = details.get("resource_links") or []
    agreement = dict(details.get("agreement") or {})
    invoices = collab.invoices or []
    finance = dict(details.get("finance") or {})
    paid_invoices = [invoice for invoice in invoices if invoice.status == "paid"]
    invoiced_amount = sum(invoice.total or 0 for invoice in invoices)
    paid_invoice_amount = sum(invoice.total or 0 for invoice in paid_invoices)
    manually_tracked = "amount_received" in finance and finance.get("amount_received") is not None
    amount_received = float(finance.get("amount_received") or 0) if manually_tracked else paid_invoice_amount
    if not manually_tracked and not paid_invoices and collab.status == "payment_received":
        amount_received = float(collab.budget or 0)
    tds_deduction = float(finance.get("tds_deduction") or 0)
    other_deductions = float(finance.get("other_deductions") or 0)
    settled_amount = amount_received + tds_deduction + other_deductions
    payment_date = finance.get("payment_date")
    if not payment_date and paid_invoices:
        payment_date = max((invoice.paid_at for invoice in paid_invoices if invoice.paid_at), default=None)
    return {
        "id": collab.id,
        "brand_id": collab.brand_id,
        "brand": collab.brand,
        "status": collab.status,
        "deliverables": collab.deliverables,
        "budget": collab.budget,
        "campaign_type": collab.campaign_type,
        "brief": collab.brief,
        "deadline": collab.deadline,
        "content_link": collab.content_link,
        "notes": collab.notes,
        "created_at": collab.created_at,
        "follow_up_at": details.get("follow_up_at"),
        "deliverable_checklist": details.get("deliverable_checklist") or [],
        "resource_links": resources,
        "performance_metrics": details.get("performance_metrics") or [],
        "activity_log": activity_log,
        "priority": details.get("priority") or "normal",
        "assignee": details.get("assignee") or "unassigned",
        "waiting_on": details.get("waiting_on") or "none",
        "next_action": details.get("next_action"),
        "stage_entered_at": stage_entered_at,
        "archived_at": collab.archived_at,
        "has_agreement": agreement.get("status") in {"draft", "sent", "signed"} or any(
            str(item.get("kind") or "").casefold() in {"contract", "agreement"}
            for item in resources if isinstance(item, dict)
        ),
        "invoice_count": len(invoices),
        "paid_invoice_count": sum(invoice.status == "paid" for invoice in invoices),
        "invoiced_amount": invoiced_amount,
        "amount_received": amount_received,
        "gross_received": amount_received + tds_deduction,
        "remaining_balance": max(float(collab.budget or 0) - settled_amount, 0),
        "payment_date": payment_date,
        "payment_method": finance.get("payment_method"),
        "tds_deduction": tds_deduction,
        "other_deductions": other_deductions,
        "finance_notes": finance.get("finance_notes"),
        "finance_tracking_enabled": "finance" in details,
    }


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


@router.get("/attention", response_model=schemas.AttentionDashboardOut)
def attention_dashboard(
    db: Session = Depends(get_db),
    admin=Depends(get_current_admin),
):
    """Prioritized manager queue built from inquiry, follow-up, deadline, and payment data."""
    now = datetime.now(timezone.utc)
    soon = now + timedelta(days=7)
    active_statuses = {
        "new", "in_discussion", "negotiating", "confirmed", "agreement_invoice",
        "script_approved", "shoot_done", "draft_submitted", "content_posted",
    }
    items = []

    collabs = (
        db.query(models.Collab)
        .options(joinedload(models.Collab.brand))
        .filter(models.Collab.status.in_(active_statuses), models.Collab.archived_at.is_(None))
        .all()
    )
    for collab in collabs:
        brand_name = collab.brand.name if collab.brand else f"Brand #{collab.brand_id}"
        created_at = _utc(collab.created_at) or now
        if collab.status == "new":
            age = now - created_at
            items.append({
                "key": f"inquiry-{collab.id}",
                "type": "inquiry",
                "source_id": collab.id,
                "brand_name": brand_name,
                "title": "New inquiry needs a response",
                "detail": collab.campaign_type or collab.deliverables or "Review the partnership request",
                "due_at": created_at,
                "urgency": "urgent" if age >= timedelta(days=2) else "soon",
                "status": collab.status,
                "href": f"/admin/collabs/{collab.id}",
            })

        follow_up_at = _utc((collab.details or {}).get("follow_up_at"))
        if follow_up_at and follow_up_at <= now:
            items.append({
                "key": f"follow-up-{collab.id}",
                "type": "follow_up",
                "source_id": collab.id,
                "brand_name": brand_name,
                "title": "Follow-up is due",
                "detail": collab.campaign_type or "Reconnect with the brand",
                "due_at": follow_up_at,
                "urgency": "urgent",
                "status": collab.status,
                "href": f"/admin/collabs/{collab.id}",
            })

        deadline = _utc(collab.deadline)
        if collab.status not in {"content_posted", "payment_received", "closed"} and deadline and deadline <= soon:
            items.append({
                "key": f"deadline-{collab.id}",
                "type": "deadline",
                "source_id": collab.id,
                "brand_name": brand_name,
                "title": "Campaign deadline passed" if deadline < now else "Campaign deadline approaching",
                "detail": collab.deliverables or collab.campaign_type or "Review campaign delivery",
                "due_at": deadline,
                "urgency": "urgent" if deadline < now else "soon",
                "status": collab.status,
                "href": f"/admin/collabs/{collab.id}",
            })

    invoices = (
        db.query(models.Invoice)
        .options(joinedload(models.Invoice.brand))
        .filter(models.Invoice.status.in_(("sent", "overdue")))
        .all()
    )
    for invoice in invoices:
        due_date = _utc(invoice.due_date)
        is_overdue = invoice.status == "overdue" or (due_date is not None and due_date < now)
        items.append({
            "key": f"payment-{invoice.id}",
            "type": "payment",
            "source_id": invoice.id,
            "brand_name": invoice.brand.name if invoice.brand else f"Brand #{invoice.brand_id}",
            "title": "Payment is overdue" if is_overdue else "Invoice awaiting payment",
            "detail": f"{invoice.invoice_number} · {invoice.payment_terms}",
            "due_at": due_date or _utc(invoice.created_at),
            "urgency": "urgent" if is_overdue else "routine",
            "status": "overdue" if is_overdue else invoice.status,
            "amount": invoice.total or 0,
            "href": "/admin/invoices",
        })

    urgency_order = {"urgent": 0, "soon": 1, "routine": 2}
    items.sort(key=lambda item: (
        urgency_order[item["urgency"]],
        item["due_at"] or now,
        item["brand_name"].casefold(),
    ))
    counts = {
        item_type: sum(item["type"] == item_type for item in items)
        for item_type in ("inquiry", "follow_up", "deadline", "payment")
    }
    return {
        "summary": {
            "total": len(items),
            "urgent": sum(item["urgency"] == "urgent" for item in items),
            "inquiries": counts["inquiry"],
            "follow_ups": counts["follow_up"],
            "deadlines": counts["deadline"],
            "payments": counts["payment"],
        },
        "items": items,
    }


@router.post("/inquiry", status_code=201)
def submit_collab_inquiry(
    payload: schemas.CollabInquiryCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Public endpoint used by the collaboration inquiry form."""
    normalized_email = str(payload.email).strip().casefold()
    brand = (
        db.query(models.Brand)
        .filter(func.lower(func.trim(models.Brand.email)) == normalized_email)
        .order_by(models.Brand.id)
        .first()
    )
    brand_reused = brand is not None

    if brand:
        # Keep the canonical brand name so past collaborations remain consistent,
        # but refresh the contact details supplied with the latest inquiry.
        brand.contact_person = payload.contact_person
        brand.email = normalized_email
        if payload.phone:
            brand.phone = payload.phone
    else:
        brand = models.Brand(
            name=payload.brand_name,
            contact_person=payload.contact_person,
            email=normalized_email,
            phone=payload.phone,
        )
        db.add(brand)
        db.flush()

    activity_log = [
        _activity(
            "inquiry_received",
            f"Inquiry received from {payload.brand_name}",
            to_status="new",
        )
    ]
    if brand_reused:
        activity_log.append(
            _activity(
                "brand_reused",
                f"Linked to existing brand profile #{brand.id} by email",
            )
        )

    collab = models.Collab(
        brand_id=brand.id,
        status="new",
        deliverables=payload.deliverables,
        budget=payload.budget,
        campaign_type=payload.campaign_type,
        deadline=payload.deadline,
        brief=payload.brief,
        details={
            "activity_log": activity_log
        },
    )
    db.add(collab)
    db.commit()
    db.refresh(collab)

    background_tasks.add_task(
        send_inquiry_notifications,
        collab.id,
        payload.model_dump(mode="json"),
    )
    return {
        "message": "Inquiry received",
        "collab_id": collab.id,
        "brand_id": brand.id,
        "brand_reused": brand_reused,
        "notifications": "queued" if email_is_configured() else "disabled",
    }


@router.post("/", response_model=schemas.CollabDetailOut, status_code=201)
def create_admin_collaboration(
    payload: schemas.AdminCollabCreate,
    db: Session = Depends(get_db),
    admin=Depends(get_current_admin),
):
    """Create a collaboration directly from the private manager workspace."""
    if payload.status not in VALID_STATUSES:
        raise HTTPException(400, f"Status must be one of {VALID_STATUSES}")
    if payload.priority not in VALID_PRIORITIES:
        raise HTTPException(400, f"Priority must be one of {sorted(VALID_PRIORITIES)}")
    if payload.assignee not in VALID_ASSIGNEES:
        raise HTTPException(400, f"Assignee must be one of {sorted(VALID_ASSIGNEES)}")
    if payload.waiting_on not in VALID_WAITING_ON:
        raise HTTPException(400, f"Waiting on must be one of {sorted(VALID_WAITING_ON)}")

    brand = None
    brand_reused = False
    if payload.brand_id:
        brand = db.query(models.Brand).filter(models.Brand.id == payload.brand_id).first()
        if not brand:
            raise HTTPException(404, "Brand not found")
        brand_reused = True
    elif payload.email:
        normalized_email = str(payload.email).strip().casefold()
        brand = (
            db.query(models.Brand)
            .filter(func.lower(func.trim(models.Brand.email)) == normalized_email)
            .order_by(models.Brand.id)
            .first()
        )
        brand_reused = brand is not None

    if not brand:
        if not payload.brand_name or not payload.brand_name.strip():
            raise HTTPException(400, "Brand name is required for a new brand")
        brand = models.Brand(
            name=payload.brand_name.strip(),
            contact_person=payload.contact_person,
            email=str(payload.email).strip().casefold() if payload.email else None,
            phone=payload.phone,
        )
        db.add(brand)
        db.flush()
    else:
        if payload.contact_person:
            brand.contact_person = payload.contact_person
        if payload.phone:
            brand.phone = payload.phone
        if payload.email:
            brand.email = str(payload.email).strip().casefold()

    activity_log = [
        _activity(
            "collaboration_added",
            "Added manually from the manager workspace",
            to_status=payload.status,
        )
    ]
    if brand_reused:
        activity_log.append(
            _activity("brand_reused", f"Linked to existing brand profile #{brand.id}")
        )

    collab = models.Collab(
        brand_id=brand.id,
        status=payload.status,
        deliverables=payload.deliverables,
        budget=payload.budget,
        campaign_type=payload.campaign_type,
        deadline=payload.deadline,
        brief=payload.brief,
        notes=payload.notes,
        details={
            "activity_log": activity_log,
            "priority": payload.priority,
            "assignee": payload.assignee,
            "waiting_on": payload.waiting_on,
            "next_action": payload.next_action,
        },
    )
    db.add(collab)
    db.commit()
    db.refresh(collab)
    collab.brand = brand
    return _detail_payload(collab)


@router.get("/", response_model=List[schemas.CollabOut])
def list_collabs(
    status: Optional[str] = None,
    archived: bool = False,
    db: Session = Depends(get_db),
    admin=Depends(get_current_admin),
):
    """Admin-only CRM pipeline view."""
    query = db.query(models.Collab).options(
        joinedload(models.Collab.brand), selectinload(models.Collab.invoices)
    )
    query = query.filter(
        models.Collab.archived_at.is_not(None) if archived else models.Collab.archived_at.is_(None)
    )
    if status:
        query = query.filter(models.Collab.status == status)
    return [_detail_payload(collab) for collab in query.order_by(models.Collab.created_at.desc()).all()]


@router.get("/{collab_id}", response_model=schemas.CollabDetailOut)
def get_collab_detail(
    collab_id: int,
    db: Session = Depends(get_db),
    admin=Depends(get_current_admin),
):
    collab = (
        db.query(models.Collab)
        .options(joinedload(models.Collab.brand), selectinload(models.Collab.invoices))
        .filter(models.Collab.id == collab_id)
        .first()
    )
    if not collab:
        raise HTTPException(404, "Collaboration not found")
    return _detail_payload(collab)


@router.post("/{collab_id}/resources", response_model=schemas.CollabDetailOut)
async def upload_collaboration_resource(
    collab_id: int,
    file: UploadFile = File(...),
    kind: str = Form("Other"),
    label: str | None = Form(None),
    db: Session = Depends(get_db),
    admin=Depends(get_current_admin),
):
    """Upload a permanent campaign brief, script, document, or supporting asset."""
    collab = (
        db.query(models.Collab)
        .options(joinedload(models.Collab.brand), selectinload(models.Collab.invoices))
        .filter(models.Collab.id == collab_id)
        .first()
    )
    if not collab:
        raise HTTPException(404, "Collaboration not found")
    if kind not in RESOURCE_KINDS:
        raise HTTPException(400, "Choose a valid resource category")

    content_type = (file.content_type or "").casefold()
    extension = ALLOWED_RESOURCE_TYPES.get(content_type)
    if not extension:
        raise HTTPException(
            400,
            "Upload a PDF, Word, Excel, PowerPoint, ZIP, text, JPG, PNG, or WebP file",
        )
    contents = await file.read(MAX_RESOURCE_BYTES + 1)
    if not contents or len(contents) > MAX_RESOURCE_BYTES:
        raise HTTPException(400, "Campaign file must be between 1 byte and 15 MB")

    original_filename = Path(file.filename or f"campaign-resource{extension}").name
    try:
        stored = store_document(
            contents,
            original_filename=original_filename,
            content_type=content_type,
            local_directory=RESOURCE_UPLOAD_DIR,
            local_url_prefix="/api/uploads/collab-resources",
            local_extension=extension,
        )
    except RuntimeError as exc:
        raise HTTPException(502, str(exc)) from exc

    details = dict(collab.details or {})
    resources = list(details.get("resource_links") or [])
    display_label = (label or "").strip() or Path(original_filename).stem
    resources.append({
        "label": display_label,
        "url": stored.url,
        "kind": kind,
        "source": "upload",
        "filename": original_filename,
        "content_type": content_type,
        "size": len(contents),
    })
    activity_log = list(details.get("activity_log") or [])
    activity_log.append(_activity("resource_uploaded", f"Uploaded {kind.lower()}: {display_label}"))
    details["resource_links"] = resources
    details["activity_log"] = activity_log[-100:]
    collab.details = details
    db.commit()
    db.refresh(collab)
    return _detail_payload(collab)


@router.patch("/{collab_id}/archive")
def archive_collaboration(
    collab_id: int,
    archived: bool = True,
    db: Session = Depends(get_db),
    admin=Depends(get_current_admin),
):
    collab = db.query(models.Collab).filter(models.Collab.id == collab_id).first()
    if not collab:
        raise HTTPException(404, "Collaboration not found")
    collab.archived_at = datetime.now(timezone.utc).replace(tzinfo=None) if archived else None
    details = dict(collab.details or {})
    activity_log = list(details.get("activity_log") or [])
    activity_log.append(_activity(
        "collaboration_archived" if archived else "collaboration_restored",
        "Moved out of the active pipeline" if archived else "Restored to the active pipeline",
    ))
    details["activity_log"] = activity_log[-100:]
    collab.details = details
    db.commit()
    return {"message": "Collaboration archived" if archived else "Collaboration restored"}


@router.delete("/{collab_id}")
def delete_collaboration(
    collab_id: int,
    db: Session = Depends(get_db),
    admin=Depends(get_current_admin),
):
    """Remove a pipeline record without deleting its brand or financial history."""
    collab = db.query(models.Collab).filter(models.Collab.id == collab_id).first()
    if not collab:
        raise HTTPException(404, "Collaboration not found")

    # Invoices and published content are historical records. Keep them, but
    # detach them before deleting the collaboration they were created from.
    db.query(models.Invoice).filter(models.Invoice.collab_id == collab_id).update(
        {models.Invoice.collab_id: None}, synchronize_session=False
    )
    db.query(models.ContentItem).filter(models.ContentItem.collab_id == collab_id).update(
        {models.ContentItem.collab_id: None}, synchronize_session=False
    )
    db.delete(collab)
    db.commit()
    return {"message": "Collaboration deleted"}


@router.patch("/{collab_id}", response_model=schemas.CollabDetailOut)
def update_collab_detail(
    collab_id: int,
    payload: schemas.CollabDetailUpdate,
    db: Session = Depends(get_db),
    admin=Depends(get_current_admin),
):
    collab = (
        db.query(models.Collab)
        .options(joinedload(models.Collab.brand))
        .filter(models.Collab.id == collab_id)
        .first()
    )
    if not collab:
        raise HTTPException(404, "Collaboration not found")

    updates = payload.model_dump(exclude_unset=True)
    details = dict(collab.details or {})
    activity_log = list(details.get("activity_log") or [])

    brand_fields = {
        "brand_name": "name",
        "brand_contact_person": "contact_person",
        "brand_email": "email",
        "brand_phone": "phone",
    }
    for payload_field, model_field in brand_fields.items():
        if payload_field in updates:
            setattr(collab.brand, model_field, updates.pop(payload_field))

    for field in (
        "campaign_type",
        "deliverables",
        "budget",
        "deadline",
        "brief",
        "content_link",
        "notes",
    ):
        if field in updates:
            setattr(collab, field, updates.pop(field))

    if "status" in updates:
        new_status = updates.pop("status")
        if new_status not in VALID_STATUSES:
            raise HTTPException(400, f"Status must be one of {VALID_STATUSES}")
        if new_status != collab.status:
            activity_log.append(
                _activity(
                    "status_changed",
                    f"Moved to {new_status.replace('_', ' ')}",
                    from_status=collab.status,
                    to_status=new_status,
                )
            )
            collab.status = new_status

    for field in (
        "follow_up_at",
        "deliverable_checklist",
        "resource_links",
        "performance_metrics",
        "priority",
        "assignee",
        "waiting_on",
        "next_action",
    ):
        if field in updates:
            value = updates.pop(field)
            if field == "priority" and value not in VALID_PRIORITIES:
                raise HTTPException(400, f"Priority must be one of {sorted(VALID_PRIORITIES)}")
            if field == "assignee" and value not in VALID_ASSIGNEES:
                raise HTTPException(400, f"Assignee must be one of {sorted(VALID_ASSIGNEES)}")
            if field == "waiting_on" and value not in VALID_WAITING_ON:
                raise HTTPException(400, f"Waiting on must be one of {sorted(VALID_WAITING_ON)}")
            if isinstance(value, list):
                value = [
                    item.model_dump() if hasattr(item, "model_dump") else item
                    for item in value
                ]
            if isinstance(value, datetime):
                value = value.isoformat()
            details[field] = value

    finance_fields = {
        "amount_received", "payment_date", "payment_method", "tds_deduction",
        "other_deductions", "finance_notes",
    }
    if finance_fields.intersection(updates):
        finance = dict(details.get("finance") or {})
        for field in finance_fields:
            if field not in updates:
                continue
            value = updates.pop(field)
            if field in {"amount_received", "tds_deduction", "other_deductions"} and value is not None and value < 0:
                raise HTTPException(400, f"{field.replace('_', ' ').title()} cannot be negative")
            if isinstance(value, datetime):
                value = value.isoformat()
            finance[field] = value
        details["finance"] = finance
        activity_log.append(_activity("finance_updated", "Collaboration payment details updated"))

    activity_log.append(_activity("details_updated", "Collaboration workspace updated"))
    details["activity_log"] = activity_log[-100:]
    collab.details = details
    db.commit()
    db.refresh(collab)
    return _detail_payload(collab)


@router.patch("/{collab_id}/status")
def update_collab_status(
    collab_id: int,
    payload: schemas.CollabStatusUpdate,
    db: Session = Depends(get_db),
    admin=Depends(get_current_admin),
):
    if payload.status not in VALID_STATUSES:
        raise HTTPException(400, f"Status must be one of {VALID_STATUSES}")
    collab = db.query(models.Collab).filter(models.Collab.id == collab_id).first()
    if not collab:
        raise HTTPException(404, "Collaboration not found")

    if payload.status != collab.status:
        details = dict(collab.details or {})
        activity_log = list(details.get("activity_log") or [])
        activity_log.append(
            _activity(
                "status_changed",
                f"Moved to {payload.status.replace('_', ' ')}",
                from_status=collab.status,
                to_status=payload.status,
            )
        )
        details["activity_log"] = activity_log[-100:]
        collab.details = details
        collab.status = payload.status
        db.commit()
    return {"message": "Status updated"}
