from sqlalchemy import Boolean, Column, Integer, String, Float, DateTime, Text, ForeignKey, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .database import Base


class Brand(Base):
    __tablename__ = "brands"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    contact_person = Column(String)
    email = Column(String)
    phone = Column(String)
    notes = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    collabs = relationship("Collab", back_populates="brand", cascade="all, delete-orphan")
    invoices = relationship("Invoice", back_populates="brand", cascade="all, delete-orphan")
    content_items = relationship("ContentItem", back_populates="brand")


class Collab(Base):
    __tablename__ = "collabs"

    id = Column(Integer, primary_key=True, index=True)
    brand_id = Column(Integer, ForeignKey("brands.id"), nullable=False)

    # Pipeline stage
    status = Column(
        String, default="new"
    )  # See VALID_STATUSES in routers/collabs.py.

    deliverables = Column(Text)   # free text, e.g. "1 Reel + 2 Stories"
    budget = Column(Float)
    deadline = Column(DateTime(timezone=True), nullable=True)
    campaign_type = Column(String)   # e.g. "Instagram Reel", "LinkedIn Post"
    brief = Column(Text)
    content_link = Column(String)    # link to live content once posted
    notes = Column(Text)
    details = Column(JSON, default=dict)  # checklist, links, performance, follow-up, activity
    archived_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    brand = relationship("Brand", back_populates="collabs")
    invoices = relationship("Invoice", back_populates="collab")
    content_items = relationship("ContentItem", back_populates="collab")


class Invoice(Base):
    __tablename__ = "invoices"

    id = Column(Integer, primary_key=True, index=True)
    invoice_number = Column(String, unique=True, index=True)
    brand_id = Column(Integer, ForeignKey("brands.id"), nullable=False)
    collab_id = Column(Integer, ForeignKey("collabs.id"), nullable=True)

    # line_items: [{"description": "...", "quantity": 1, "rate": 5000}]
    line_items = Column(JSON, nullable=False)

    subtotal = Column(Float)
    tax_percent = Column(Float, default=0)
    total = Column(Float)

    payment_terms = Column(String, default="Due within 15 days")
    due_date = Column(DateTime(timezone=True), nullable=True)
    status = Column(String, default="draft")  # draft, sent, paid, overdue

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    paid_at = Column(DateTime(timezone=True), nullable=True)
    sent_at = Column(DateTime(timezone=True), nullable=True)
    last_reminded_at = Column(DateTime(timezone=True), nullable=True)
    reminder_count = Column(Integer, default=0, nullable=False)
    email_message_id = Column(String, nullable=True)

    brand = relationship("Brand", back_populates="invoices")
    collab = relationship("Collab", back_populates="invoices")


class MediaKitContent(Base):
    """
    Single-row settings table for everything editable on the public
    media kit page (bio, rate card, testimonials, manual stats like
    LinkedIn which has no public API).
    """
    __tablename__ = "media_kit_content"

    id = Column(Integer, primary_key=True, default=1)
    name = Column(String, default="Aarohi Dixit")
    tagline = Column(String, default="Tech Content Creator")
    bio = Column(Text, default="")
    location = Column(String, default="")

    # manual stats fallback / LinkedIn (no public API)
    linkedin_followers = Column(Integer, default=0)
    linkedin_avg_impressions = Column(Integer, default=0)

    rate_card = Column(JSON, default=list)          # [{"deliverable": "...", "price": ...}]
    testimonials = Column(JSON, default=list)        # [{"brand": "...", "quote": "...", "author": "..."}]
    past_collabs = Column(JSON, default=list)        # [{"brand": "...", "logo_url": "...", "summary": "..."}]

    instagram_handle = Column(String, default="")
    youtube_handle = Column(String, default="")
    linkedin_handle = Column(String, default="")

    # Flexible admin-managed sections such as contact details, social links,
    # performance highlights, audience insights, and uploaded media.
    extras = Column(JSON, default=dict)
    # Complete working copy used by the manager/Aarohi approval workflow.
    # Published columns above remain the source for the public media kit.
    draft_content = Column(JSON, nullable=True)
    published_at = Column(DateTime(timezone=True), nullable=True)
    published_by = Column(String, nullable=True)


class ContentItem(Base):
    __tablename__ = "content_items"

    id = Column(Integer, primary_key=True, index=True)
    brand_id = Column(Integer, ForeignKey("brands.id"), nullable=True)
    collab_id = Column(Integer, ForeignKey("collabs.id"), nullable=True)
    platform = Column(String, nullable=False)
    title = Column(String, nullable=False)
    content_url = Column(String)
    thumbnail_url = Column(String)
    published_at = Column(DateTime(timezone=True), nullable=True)
    objective = Column(Text)
    results = Column(Text)
    notes = Column(Text)
    metrics = Column(JSON, default=dict)
    featured = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    brand = relationship("Brand", back_populates="content_items")
    collab = relationship("Collab", back_populates="content_items")


class SocialStatCache(Base):
    __tablename__ = "social_stat_cache"

    id = Column(Integer, primary_key=True, index=True)
    platform = Column(String, unique=True, nullable=False, index=True)
    status = Column(String, default="disconnected", nullable=False)
    data = Column(JSON, default=dict)
    error = Column(Text)
    last_attempted_at = Column(DateTime(timezone=True), nullable=True)
    last_synced_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class SocialStatSnapshot(Base):
    __tablename__ = "social_stat_snapshots"

    id = Column(Integer, primary_key=True, index=True)
    platform = Column(String, nullable=False, index=True)
    followers = Column(Integer, default=0, nullable=False)
    total_views = Column(Integer, nullable=True)
    media_count = Column(Integer, nullable=True)
    captured_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
