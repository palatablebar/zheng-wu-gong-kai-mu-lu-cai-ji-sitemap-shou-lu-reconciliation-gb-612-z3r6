"""sitemap 条目服务（B 集合）：登记与查询。"""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.models.site import Site
from src.models.sitemap_entry import SitemapEntry
from src.services.url_normalize import normalize_url
from src.utils.errors import AppError, not_found
from src.utils.timeutil import iso_utc


def serialize(entry: SitemapEntry, site_name: str | None = None, site_code: str | None = None) -> dict:
    return {
        "id": entry.id,
        "site_id": entry.site_id,
        "site_name": site_name,
        "site_code": site_code,
        "loc": entry.loc,
        "canonical_url": entry.canonical_url,
        "lastmod": entry.lastmod,
        "changefreq": entry.changefreq,
        "priority": entry.priority,
        "source_file": entry.source_file,
        "created_at": iso_utc(entry.created_at),
    }


def list_entries(
    db: Session,
    *,
    site_id: int | None = None,
    q: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> dict:
    stmt = select(SitemapEntry)
    count_stmt = select(func.count()).select_from(SitemapEntry)
    if site_id:
        stmt = stmt.where(SitemapEntry.site_id == site_id)
        count_stmt = count_stmt.where(SitemapEntry.site_id == site_id)
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(SitemapEntry.loc.ilike(like))
        count_stmt = count_stmt.where(SitemapEntry.loc.ilike(like))
    total = db.scalar(count_stmt) or 0
    rows = db.scalars(stmt.order_by(SitemapEntry.site_id, SitemapEntry.id).limit(limit).offset(offset)).all()
    sites = {site.id: site for site in db.scalars(select(Site)).all()}
    return {
        "items": [
            serialize(
                row,
                sites.get(row.site_id).name if sites.get(row.site_id) else None,
                sites.get(row.site_id).code if sites.get(row.site_id) else None,
            )
            for row in rows
        ],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


def create_entry(db: Session, payload: dict) -> SitemapEntry:
    site = db.get(Site, int(payload["site_id"]))
    if site is None:
        raise not_found("site", payload.get("site_id"))
    loc = payload["loc"].strip()
    exists = db.scalar(select(SitemapEntry).where(SitemapEntry.site_id == site.id, SitemapEntry.loc == loc))
    if exists is not None:
        raise AppError("CONFLICT", 409, {"loc": loc})
    entry = SitemapEntry(
        site_id=site.id,
        loc=loc,
        canonical_url=normalize_url(payload.get("canonical_url") or loc),
        lastmod=payload.get("lastmod"),
        changefreq=payload.get("changefreq") or "weekly",
        priority=float(payload.get("priority") or 0.8),
        source_file=payload.get("source_file") or "sitemap.xml",
    )
    db.add(entry)
    db.flush()
    return entry
