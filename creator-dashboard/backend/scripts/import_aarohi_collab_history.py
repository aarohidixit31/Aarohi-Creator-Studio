"""Import Aarohi's verified 2025-2026 collaboration history.

The importer is intentionally idempotent: each record has a stable source key,
so running ``--apply`` more than once will not duplicate collaborations.
Run without ``--apply`` to preview the changes.
"""

from __future__ import annotations

import argparse
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import func


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app import models  # noqa: E402
from app.database import SessionLocal, engine  # noqa: E402
from app.routers.brands import _add_media_kit_collab  # noqa: E402


def dt(value: str) -> datetime:
    return datetime.fromisoformat(value).replace(tzinfo=timezone.utc)


def record(
    key: str,
    brand: str,
    date: str,
    campaign: str,
    *,
    amount: float | None = None,
    link: str | None = None,
    links: list[tuple[str, str]] | None = None,
    notes: str | None = None,
    deliverables: str = "Instagram Reel",
    deadline: str | None = None,
    compensation: str = "paid",
    date_precision: str = "day",
) -> dict:
    return {
        "key": f"aarohi-history-v1:{key}",
        "brand": brand,
        "date": date,
        "date_precision": date_precision,
        "campaign": campaign,
        "amount": amount,
        "link": link,
        "links": links or [],
        "notes": notes,
        "deliverables": deliverables,
        "deadline": deadline,
        "compensation": compensation,
    }


RECORDS = [
    # 2025: the supplied month is retained as month-level precision.
    record("2025-golzza", "Golzza", "2025-03-01", "Chitkara University outlet campaign", amount=18000,
           notes="Collaboration ran March–July 2025; outlet at Chitkara University.", deadline="2025-07-31", date_precision="range"),
    record("2025-career-roadmap-may", "Career Roadmap", "2025-05-01", "Career Roadmap: May", amount=1000,
           link="https://www.instagram.com/p/DI_gcXgPGuq/", notes="Contact: Hemang.", date_precision="month"),
    record("2025-career-roadmap-june", "Career Roadmap", "2025-06-01", "Career Roadmap: June", amount=700,
           link="https://www.instagram.com/p/DJZKTS8P6gL/", links=[("Additional Career Roadmap content", "https://www.instagram.com/reel/DLH7LDovtHz/")],
           notes="Contact: Hemang.", date_precision="month"),
    record("2025-career-roadmap-august", "Career Roadmap", "2025-08-01", "Career Roadmap: August", amount=2800,
           link="https://www.instagram.com/p/DMsijf5v-Z2/", notes="Contact: Hemang.", date_precision="month"),
    record("2025-kpit-sparkle", "KPIT", "2025-11-01", "KPIT Sparkle promotional reel", amount=6500,
           link="https://www.instagram.com/p/DQy9gGJD2nS/", date_precision="month"),
    record("2025-geeksforgeeks", "GeeksforGeeks", "2025-09-01", "GeeksforGeeks campaign", amount=6000,
           link="https://www.instagram.com/reel/DOdsfKyD01J/", date_precision="month"),
    record("2025-codeflix-labs", "Codeflix Labs", "2025-07-01", "Codeflix Labs promotional reel", amount=3500,
           link="https://www.instagram.com/reel/DMNlEJUvTju/", notes="Previously listed as CodeChef; corrected to Codeflix Labs.", date_precision="month"),
    record("2025-code-monsters", "Code Monsters", "2025-08-01", "Hackathon promotional reel", amount=4000,
           link="https://www.instagram.com/p/DM7xAnzvSQg/", date_precision="month"),
    record("2025-superprofile", "SuperProfile", "2025-12-01", "SuperProfile campaign", amount=3000,
           link="https://www.instagram.com/p/DSkLmtNEZuX/", date_precision="month"),
    record("2025-finalround-ai", "FinalRound AI", "2025-07-01", "Interview Reels", amount=12000,
           notes="Interview-focused promotional Reels.", date_precision="month"),
    record("2025-coding-ninjas-barter", "Coding Ninjas", "2025-04-01", "Goodies barter collaboration",
           link="https://www.instagram.com/p/DIgohHGR6B9/", notes="Barter collaboration; compensation received as Coding Ninjas goodies, not cash.",
           compensation="barter", date_precision="estimated_month"),
    record("2025-chitkara-unpaid", "Chitkara University", "2025-10-01", "Chitkara University collaboration",
           link="https://www.instagram.com/reel/DPgQJ8ijCgw/", notes="Unpaid collaboration; month estimated from the supplied post sequence.",
           compensation="unpaid", date_precision="estimated_month"),

    # 2026: the amountless 26 February SuperProfile note is deliberately omitted.
    record("2026-chitkara-unpaid", "Chitkara University", "2026-01-01", "Chitkara University collaboration",
           link="https://www.instagram.com/p/DTKJcLGksRa/", notes="Unpaid collaboration; month estimated from the supplied post sequence.",
           compensation="unpaid", date_precision="estimated_month"),
    record("2026-motorola-launch", "Motorola", "2026-03-02", "New phone launch promotional Reels", amount=14000,
           link="https://www.instagram.com/reel/DVk9hwvkVIf/", links=[("Motorola launch Reel 3", "https://www.instagram.com/reel/DVbAbfQEVz4/")],
           notes="Combined campaign. Payments received: ₹4,000 on 2 Mar, ₹6,000 on 10 Mar, and ₹4,000 on 16 Mar 2026.",
           deliverables="3 Instagram Reels", deadline="2026-03-16"),
    record("2026-brand-bikega-ugsot", "Brand Bikega", "2026-04-02", "UGSOT Reel", amount=7000,
           link="https://www.instagram.com/p/DWqC_agEdpg/", notes="UGSOT campaign delivered through Brand Bikega."),
    record("2026-unstop", "Unstop", "2026-04-30", "IPL promotional campaign", amount=2000,
           link="https://www.instagram.com/p/DXZctB0j-sb/"),
    record("2026-linkedin", "LinkedIn", "2026-05-10", "LinkedIn collaboration", amount=2500,
           deliverables="Brand collaboration"),
    record("2026-bits-launchpad", "BITS Pilani Hyderabad", "2026-05-03", "Launchpad 26 event coverage",
           link="https://www.instagram.com/p/DWwU0JcDy4_/", notes="Visited BITS Pilani Hyderabad on 3–4 May 2026 and covered Launchpad 26.",
           deliverables="On-site event coverage", deadline="2026-05-04", compensation="unreported"),
    record("2026-stanford-unpaid", "Stanford University", "2026-04-01", "Stanford University collaboration",
           link="https://www.instagram.com/p/DWlpG3BER9q/", notes="Unpaid collaboration; month estimated from the supplied post sequence.",
           compensation="unpaid", date_precision="estimated_month"),
    record("2026-vgu", "VGU Rajasthan", "2026-06-29", "VGU Jaipur promotional reel", amount=6000,
           link="https://www.instagram.com/reel/DaDLXnVoTAJ/", notes="Campaign delivered through Brand Bikega."),
    record("2026-ganpat", "Ganpat University", "2026-07-04", "Ganpat University Goa promotional reel", amount=6000,
           link="https://www.instagram.com/reel/DaVK74KS0Mx/", notes="Campaign delivered through Brand Bikega."),
    record("2026-aakash", "Aakash Institute", "2026-07-16", "Aakash Institute promotional reel", amount=7000,
           link="https://www.instagram.com/reel/Da0JvR7PDhM/"),
    record("2026-superprofile", "SuperProfile", "2026-07-31", "SuperProfile campaign", amount=3000,
           link="https://www.instagram.com/reel/DVNiAPqkdip/"),
]


def normalized_name(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.casefold())


def import_history(*, apply: bool) -> dict:
    db = SessionLocal()
    summary = {"brands_created": 0, "brands_reused": 0, "collabs_created": 0, "duplicates_skipped": 0,
               "media_kit_added": 0, "cash_total": 0.0, "barter": 0, "unpaid": 0, "unreported": 0}
    try:
        brands = {normalized_name(item.name): item for item in db.query(models.Brand).order_by(models.Brand.id).all()}
        existing_keys = {
            str((item.details or {}).get("import_key"))
            for item in db.query(models.Collab).all()
            if (item.details or {}).get("import_key")
        }

        for item in RECORDS:
            if item["key"] in existing_keys:
                summary["duplicates_skipped"] += 1
                continue

            brand_key = normalized_name(item["brand"])
            brand = brands.get(brand_key)
            if brand is None:
                brand = models.Brand(name=item["brand"])
                db.add(brand)
                db.flush()
                brands[brand_key] = brand
                summary["brands_created"] += 1
            else:
                summary["brands_reused"] += 1

            amount = item["amount"]
            compensation = item["compensation"]
            event_time = dt(item["date"])
            resources = []
            if item["link"]:
                resources.append({"label": "Published Instagram content", "url": item["link"], "kind": "Live content", "source": "link"})
            resources.extend(
                {"label": label, "url": url, "kind": "Live content", "source": "link"}
                for label, url in item["links"]
                if url != item["link"]
            )
            finance = {
                "amount_received": amount if compensation == "paid" else 0,
                "payment_date": event_time.isoformat() if compensation == "paid" else None,
                "payment_method": None,
                "tds_deduction": 0,
                "other_deductions": 0,
                "finance_notes": item["notes"] or ("Historical payment marked received." if compensation == "paid" else None),
            }
            details = {
                "import_key": item["key"],
                "import_source": "Aarohi supplied collaboration history",
                "date_precision": item["date_precision"],
                "compensation_type": compensation,
                "resource_links": resources,
                "finance": finance,
                "priority": "normal",
                "assignee": "unassigned",
                "waiting_on": "none",
                "activity_log": [{
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "action": "history_imported",
                    "detail": "Imported from Aarohi's verified 2025–2026 collaboration history",
                    "to_status": "payment_received" if compensation == "paid" else "closed",
                }],
            }
            collab = models.Collab(
                brand_id=brand.id,
                status="payment_received" if compensation == "paid" else "closed",
                campaign_type=item["campaign"],
                deliverables=item["deliverables"],
                budget=amount,
                deadline=dt(item["deadline"]) if item["deadline"] else None,
                content_link=item["link"],
                notes=item["notes"],
                details=details,
                created_at=event_time,
            )
            db.add(collab)
            db.flush()
            existing_keys.add(item["key"])
            summary["collabs_created"] += 1
            if compensation == "paid":
                summary["cash_total"] += float(amount or 0)
            else:
                summary[compensation] += 1

            if item["link"]:
                added = _add_media_kit_collab(db, {
                    "brand": brand.name,
                    "logo_url": None,
                    "image_url": None,
                    "content_url": item["link"],
                    "summary": item["campaign"],
                    "visible": True,
                })
                summary["media_kit_added"] += int(added)

        if apply:
            db.commit()
        else:
            db.rollback()
        return summary
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Commit the import; without this flag all changes are rolled back")
    args = parser.parse_args()
    print(f"Database: {engine.url.get_backend_name()} ({engine.url.host or 'local file'})")
    print("Mode:", "APPLY" if args.apply else "DRY RUN")
    for name, value in import_history(apply=args.apply).items():
        print(f"{name}: {value}")
