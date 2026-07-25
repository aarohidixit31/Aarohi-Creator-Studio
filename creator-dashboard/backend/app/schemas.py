from pydantic import BaseModel, ConfigDict, EmailStr, Field
from typing import Optional, List
from datetime import datetime


# ---------- Brand ----------
class BrandCreate(BaseModel):
    name: str
    contact_person: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    notes: Optional[str] = None


class BrandOut(BrandCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime


class BrandUpdate(BaseModel):
    name: Optional[str] = None
    contact_person: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    notes: Optional[str] = None


class BrandDirectoryOut(BrandOut):
    collaboration_count: int = 0
    active_collaboration_count: int = 0
    invoice_count: int = 0
    total_invoiced: float = 0
    total_received: float = 0
    outstanding_amount: float = 0
    last_activity_at: Optional[datetime] = None


# ---------- Collab inquiry (public form) ----------
class CollabInquiryCreate(BaseModel):
    brand_name: str
    contact_person: str
    email: EmailStr
    phone: Optional[str] = None
    budget: Optional[float] = None
    campaign_type: Optional[str] = None
    deliverables: Optional[str] = None
    deadline: Optional[datetime] = None
    brief: Optional[str] = None


class AdminCollabCreate(BaseModel):
    brand_id: Optional[int] = None
    brand_name: Optional[str] = None
    contact_person: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    status: str = "new_inquiry"
    budget: Optional[float] = None
    campaign_type: Optional[str] = None
    deliverables: Optional[str] = None
    deadline: Optional[datetime] = None
    brief: Optional[str] = None
    notes: Optional[str] = None


class CollabOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    brand_id: int
    brand: BrandOut
    status: str
    deliverables: Optional[str]
    budget: Optional[float]
    campaign_type: Optional[str]
    brief: Optional[str]
    deadline: Optional[datetime]
    content_link: Optional[str]
    notes: Optional[str]
    created_at: datetime

class CollabStatusUpdate(BaseModel):
    status: str


class DeliverableTask(BaseModel):
    text: str
    completed: bool = False


class ResourceLink(BaseModel):
    label: str
    url: str
    kind: Optional[str] = None


class PerformanceMetric(BaseModel):
    label: str
    value: str


class ActivityEvent(BaseModel):
    timestamp: datetime
    action: str
    detail: Optional[str] = None
    from_status: Optional[str] = None
    to_status: Optional[str] = None


class CollabDetailOut(CollabOut):
    follow_up_at: Optional[datetime] = None
    deliverable_checklist: List[DeliverableTask] = Field(default_factory=list)
    resource_links: List[ResourceLink] = Field(default_factory=list)
    performance_metrics: List[PerformanceMetric] = Field(default_factory=list)
    activity_log: List[ActivityEvent] = Field(default_factory=list)


class CollabDetailUpdate(BaseModel):
    brand_name: Optional[str] = None
    brand_contact_person: Optional[str] = None
    brand_email: Optional[EmailStr] = None
    brand_phone: Optional[str] = None
    campaign_type: Optional[str] = None
    deliverables: Optional[str] = None
    budget: Optional[float] = None
    deadline: Optional[datetime] = None
    status: Optional[str] = None
    brief: Optional[str] = None
    content_link: Optional[str] = None
    notes: Optional[str] = None
    follow_up_at: Optional[datetime] = None
    deliverable_checklist: Optional[List[DeliverableTask]] = None
    resource_links: Optional[List[ResourceLink]] = None
    performance_metrics: Optional[List[PerformanceMetric]] = None


# ---------- Invoice ----------
class LineItem(BaseModel):
    description: str
    quantity: float = 1
    rate: float


class InvoiceCreate(BaseModel):
    brand_id: int
    collab_id: Optional[int] = None
    line_items: List[LineItem]
    tax_percent: float = 0
    payment_terms: str = "Due within 15 days"
    due_date: Optional[datetime] = None


class InvoiceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    invoice_number: str
    brand_id: int
    collab_id: Optional[int]
    line_items: List[LineItem]
    subtotal: float
    tax_percent: float
    total: float
    payment_terms: str
    due_date: Optional[datetime]
    status: str
    created_at: datetime
    paid_at: Optional[datetime] = None
    sent_at: Optional[datetime] = None
    last_reminded_at: Optional[datetime] = None
    reminder_count: int = 0
    email_message_id: Optional[str] = None


class InvoiceDeliveryOut(BaseModel):
    message: str
    status: str
    recipient: EmailStr
    message_id: Optional[str] = None
    sent_at: Optional[datetime] = None
    last_reminded_at: Optional[datetime] = None
    reminder_count: int = 0

class InvoiceListOut(InvoiceOut):
    brand: BrandOut


class InvoiceLedgerOut(BaseModel):
    total_invoiced: float
    total_received: float
    total_outstanding: float
    total_draft: float
    invoice_count: int
    paid_count: int
    outstanding_count: int


class AttentionItem(BaseModel):
    key: str
    type: str
    source_id: int
    brand_name: str
    title: str
    detail: str
    due_at: Optional[datetime] = None
    urgency: str
    status: Optional[str] = None
    amount: Optional[float] = None
    href: str


class AttentionSummary(BaseModel):
    total: int
    urgent: int
    inquiries: int
    follow_ups: int
    deadlines: int
    payments: int


class AttentionDashboardOut(BaseModel):
    summary: AttentionSummary
    items: List[AttentionItem] = Field(default_factory=list)


# ---------- Content history ----------
class ContentMetrics(BaseModel):
    views: Optional[int] = None
    reach: Optional[int] = None
    likes: Optional[int] = None
    comments: Optional[int] = None
    saves: Optional[int] = None
    shares: Optional[int] = None
    conversions: Optional[int] = None
    engagement_rate: Optional[float] = None


class ContentCreate(BaseModel):
    brand_id: Optional[int] = None
    collab_id: Optional[int] = None
    platform: str
    title: str
    content_url: Optional[str] = None
    thumbnail_url: Optional[str] = None
    published_at: Optional[datetime] = None
    objective: Optional[str] = None
    results: Optional[str] = None
    notes: Optional[str] = None
    metrics: ContentMetrics = Field(default_factory=ContentMetrics)
    featured: bool = False


class ContentUpdate(BaseModel):
    brand_id: Optional[int] = None
    collab_id: Optional[int] = None
    platform: Optional[str] = None
    title: Optional[str] = None
    content_url: Optional[str] = None
    thumbnail_url: Optional[str] = None
    published_at: Optional[datetime] = None
    objective: Optional[str] = None
    results: Optional[str] = None
    notes: Optional[str] = None
    metrics: Optional[ContentMetrics] = None
    featured: Optional[bool] = None


class ContentOut(ContentCreate):
    id: int
    brand: Optional[BrandOut] = None
    collab_label: Optional[str] = None
    created_at: datetime


class ContentLibrarySummary(BaseModel):
    content_count: int
    featured_count: int
    total_views: int
    total_reach: int
    average_engagement_rate: float
    top_content_id: Optional[int] = None


# ---------- Live social statistics ----------
class SocialStatOut(BaseModel):
    platform: str
    configured: bool
    status: str
    data: dict = Field(default_factory=dict)
    error: Optional[str] = None
    last_attempted_at: Optional[datetime] = None
    last_synced_at: Optional[datetime] = None
    cache_hours: int


class SocialStatSnapshotOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    platform: str
    followers: int
    total_views: Optional[int] = None
    media_count: Optional[int] = None
    captured_at: datetime


class BrandDetailOut(BrandDirectoryOut):
    collabs: List[CollabOut] = Field(default_factory=list)
    invoices: List[InvoiceOut] = Field(default_factory=list)


# ---------- Media kit ----------
class RateCardItem(BaseModel):
    deliverable: str
    price: Optional[float] = None
    note: Optional[str] = None  # e.g. "Custom quote"
    visible: bool = True


class Testimonial(BaseModel):
    brand: str
    quote: str
    author: Optional[str] = None
    visible: bool = True


class PastCollab(BaseModel):
    brand: str
    logo_url: Optional[str] = None
    image_url: Optional[str] = None
    content_url: Optional[str] = None
    summary: Optional[str] = None
    visible: bool = True


class SocialLink(BaseModel):
    platform: str
    label: Optional[str] = None
    handle: Optional[str] = None
    url: str
    follower_count: Optional[int] = None
    secondary_stat: Optional[str] = None
    visible: bool = True


class MediaHighlight(BaseModel):
    label: str
    value: str
    note: Optional[str] = None
    visible: bool = True


class AudienceInsight(BaseModel):
    label: str
    value: str
    visible: bool = True


class GalleryItem(BaseModel):
    title: str
    image_url: str
    category: Optional[str] = None
    caption: Optional[str] = None
    link_url: Optional[str] = None
    visible: bool = True


class MediaKitUpdate(BaseModel):
    name: Optional[str] = None
    tagline: Optional[str] = None
    bio: Optional[str] = None
    location: Optional[str] = None
    linkedin_followers: Optional[int] = None
    linkedin_avg_impressions: Optional[int] = None
    rate_card: Optional[List[RateCardItem]] = None
    testimonials: Optional[List[Testimonial]] = None
    past_collabs: Optional[List[PastCollab]] = None
    instagram_handle: Optional[str] = None
    youtube_handle: Optional[str] = None
    linkedin_handle: Optional[str] = None
    contact_email: Optional[EmailStr] = None
    contact_phone: Optional[str] = None
    profile_image_url: Optional[str] = None
    cover_image_url: Optional[str] = None
    social_links: Optional[List[SocialLink]] = None
    highlights: Optional[List[MediaHighlight]] = None
    audience_insights: Optional[List[AudienceInsight]] = None
    gallery: Optional[List[GalleryItem]] = None
    content_pillars: Optional[List[str]] = None
    partner_reasons: Optional[List[str]] = None
    section_order: Optional[List[str]] = None
    hidden_sections: Optional[List[str]] = None
