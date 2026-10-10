"""Website content managed by the super admin (Admin → Website): policy pages (Markdown with placeholders) and the
home page texts (JSON). Every save keeps the previous version; any version can be restored or the built-in text brought
back. Built-in texts live in app/content/*.md (policies) and in the frontend (home page).

Placeholders in policy pages (filled in by the browser from the live settings):
    {{brand}}  {{company.name|email|address|phone}}  {{legal.grievance_officer|grievance_email|grievance_phone|
    jurisdiction|data_location|cin}}  {{legal.jurisdiction|fallback text}}  {{#if legal.cin}}…{{/if}}
"""

import datetime as dt
import json
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from ..deps import DB, platform_area
from ..models import SitePage, SitePageVersion
from ..services import config_store as C
from ..services import platform_team
from ..services.platform_audit import log

WebsiteTeam = platform_area("website")  # super admin, or team members with the website area
router = APIRouter(tags=["website"])
CONTENT = Path(__file__).resolve().parent.parent / "content"
PAGES = {"landing": "Home page", "terms": "Terms of Service", "privacy": "Privacy Policy", "dpa": "Data Processing Addendum",
         "security": "Security & Data Retention", "grievance": "Grievance Redressal", "refund": "Refund & Cancellation Policy",
         "disclaimer": "Disclaimer", "contact": "Contact us"}
CONSENT_PAGES = {"terms", "privacy", "dpa"}  # changing these can ask every user to accept again


def _default(slug: str) -> str | None:
    p = CONTENT / f"{slug}.md"
    return p.read_text(encoding="utf-8") if p.exists() else None


def _page(db, slug: str) -> dict:
    if slug not in PAGES:
        raise HTTPException(404, "Page not found")
    row = db.get(SitePage, slug)
    return {"slug": slug, "title": row.title if row else PAGES[slug], "body": row.body if row else _default(slug),
            "custom": row is not None, "updated_at": row.updated_at if row else None, "updated_by": row.updated_by if row else None,
            "format": "json" if slug == "landing" else "markdown"}


@router.get("/site/{slug}")
def public_page(slug: str, db: DB):
    """Public: the text of a website page."""
    p = _page(db, slug)
    p.pop("updated_by")
    return p


# ---------------------------------------------------------------- super admin
@router.get("/admin/site")
def pages(db: DB, _: WebsiteTeam):
    counts = dict(db.execute(select(SitePageVersion.slug, func.count(SitePageVersion.id)).group_by(SitePageVersion.slug)).all())
    out = []
    for slug in PAGES:
        p = _page(db, slug)
        out.append({k: p[k] for k in ("slug", "title", "custom", "updated_at", "updated_by", "format")} | {"versions": counts.get(slug, 0),
                   "consent": slug in CONSENT_PAGES})
    return {"pages": out, "legal_version": (C.get("legal") or {}).get("version")}


@router.get("/admin/site/{slug}")
def page(slug: str, db: DB, _: WebsiteTeam):
    return {**_page(db, slug), "default_body": _default(slug), "consent": slug in CONSENT_PAGES}


class PageIn(BaseModel):
    title: str = Field(min_length=2, max_length=120)
    body: str = Field(max_length=300_000)
    note: str | None = Field(None, max_length=300)
    reaccept: bool = False  # Terms / Privacy / DPA: every user accepts the new version at next sign-in


def _snapshot(db, slug: str, by: str, note: str | None) -> None:
    cur = _page(db, slug)
    if cur["body"] is not None:
        db.add(SitePageVersion(slug=slug, title=cur["title"], body=cur["body"], saved_by=by, note=note))


def _store(db, slug: str, title: str, body: str, by: str) -> SitePage:
    row = db.get(SitePage, slug) or SitePage(slug=slug)
    row.title, row.body, row.updated_by, row.updated_at = title, body, by, dt.datetime.now(dt.UTC)
    db.add(row)
    return row


def _bump_legal(db, admin) -> str:
    legal = dict(C.get("legal") or {})
    legal["version"] = dt.datetime.now(dt.timezone(dt.timedelta(hours=5, minutes=30))).strftime("%Y-%m-%d.%H%M")
    C.add_version(db, dt.date.today(), {"legal": legal}, "Policy updated — users accept again", admin.email)
    return legal["version"]


@router.put("/admin/site/{slug}")
def save(slug: str, data: PageIn, db: DB, admin: WebsiteTeam, request: Request):
    _page(db, slug)
    if data.reaccept and not platform_team.is_superadmin(admin):
        raise HTTPException(403, "Only the super admin can ask every user to accept the policies again")
    if slug == "landing":
        try:
            if not isinstance(json.loads(data.body), dict):
                raise ValueError
        except ValueError:
            raise HTTPException(422, "Home page content must be a JSON object") from None
    _snapshot(db, slug, admin.name, data.note or "Before an edit")
    _store(db, slug, data.title, data.body, admin.name)
    version = _bump_legal(db, admin) if data.reaccept and slug in CONSENT_PAGES else None
    log(db, admin, "CONFIG", "website", f"Website page edited: {PAGES[slug]}" + (f" — users accept again (v{version})" if version else ""),
        request=request)
    db.commit()
    return {**_page(db, slug), "legal_version": version}


@router.get("/admin/site/{slug}/versions")
def versions(slug: str, db: DB, _: WebsiteTeam):
    rows = db.scalars(select(SitePageVersion).where(SitePageVersion.slug == slug).order_by(SitePageVersion.saved_at.desc()).limit(100))
    return [dict(id=v.id, title=v.title, saved_at=v.saved_at, saved_by=v.saved_by, note=v.note, size=len(v.body)) for v in rows]


@router.get("/admin/site/{slug}/versions/{vid}")
def version(slug: str, vid: str, db: DB, _: WebsiteTeam):
    v = db.get(SitePageVersion, vid)
    if not v or v.slug != slug:
        raise HTTPException(404, "Version not found")
    return dict(id=v.id, title=v.title, body=v.body, saved_at=v.saved_at, saved_by=v.saved_by, note=v.note)


@router.post("/admin/site/{slug}/versions/{vid}/restore")
def restore(slug: str, vid: str, db: DB, admin: WebsiteTeam, request: Request):
    v = db.get(SitePageVersion, vid)
    if not v or v.slug != slug:
        raise HTTPException(404, "Version not found")
    _snapshot(db, slug, admin.name, "Before restoring an older version")
    _store(db, slug, v.title, v.body, admin.name)
    log(db, admin, "CONFIG", "website", f"Website page restored to an older version: {PAGES[slug]}", request=request)
    db.commit()
    return _page(db, slug)


@router.post("/admin/site/{slug}/reset")
def reset(slug: str, db: DB, admin: WebsiteTeam, request: Request):
    """Back to the built-in text (the current text is kept as a version)."""
    row = db.get(SitePage, slug)
    if row:
        _snapshot(db, slug, admin.name, "Before going back to the built-in text")
        db.delete(row)
        log(db, admin, "CONFIG", "website", f"Website page back to built-in text: {PAGES[slug]}", request=request)
        db.commit()
    return _page(db, slug)
