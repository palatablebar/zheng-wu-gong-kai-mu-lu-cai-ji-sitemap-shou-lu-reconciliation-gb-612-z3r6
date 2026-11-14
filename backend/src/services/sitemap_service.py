"""sitemap 条目服务（B 集合）：生效地址查询、手工登记、轮次与子清单留痕查询。"""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.models.site import Site
from src.models.sitemap_entry import SitemapEntry
from src.models.sitemap_round import SitemapRound
from src.models.sitemap_source import SitemapSource, SitemapVersion
from src.services import sitemap_sync
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
        "is_gap": entry.is_gap,
        "created_at": iso_utc(entry.created_at),
        "updated_at": iso_utc(entry.updated_at),
    }


def list_entries(
    db: Session,
    *,
    site_id: int | None = None,
    q: str | None = None,
    source_file: str | None = None,
    is_gap: bool | None = None,
    limit: int = 20,
    offset: int = 0,
) -> dict:
    stmt = select(SitemapEntry)
    count_stmt = select(func.count()).select_from(SitemapEntry)
    if site_id:
        stmt = stmt.where(SitemapEntry.site_id == site_id)
        count_stmt = count_stmt.where(SitemapEntry.site_id == site_id)
    if source_file:
        stmt = stmt.where(SitemapEntry.source_file == source_file)
        count_stmt = count_stmt.where(SitemapEntry.source_file == source_file)
    if is_gap is not None:
        stmt = stmt.where(SitemapEntry.is_gap.is_(is_gap))
        count_stmt = count_stmt.where(SitemapEntry.is_gap.is_(is_gap))
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
    canonical_url = normalize_url(payload.get("canonical_url") or loc)
    exists = db.scalar(
        select(SitemapEntry).where(
            SitemapEntry.site_id == site.id, SitemapEntry.canonical_url == canonical_url
        )
    )
    if exists is not None:
        raise AppError("CONFLICT", 409, {"canonical_url": canonical_url})
    entry = SitemapEntry(
        site_id=site.id,
        loc=loc,
        canonical_url=canonical_url,
        lastmod=payload.get("lastmod"),
        changefreq=payload.get("changefreq") or "weekly",
        priority=float(payload.get("priority") or 0.8),
        source_file=payload.get("source_file") or "manual.xml",
        is_gap=False,
    )
    db.add(entry)
    db.flush()
    return entry


def list_sources(db: Session, *, site_id: int) -> dict:
    rows = db.scalars(
        select(SitemapSource).where(SitemapSource.site_id == site_id).order_by(SitemapSource.source_file)
    ).all()
    return {"items": [sitemap_sync.serialize_source(row) for row in rows], "total": len(rows)}


def list_rounds(db: Session, *, site_id: int | None = None, limit: int = 20) -> dict:
    stmt = select(SitemapRound)
    count_stmt = select(func.count()).select_from(SitemapRound)
    if site_id:
        stmt = stmt.where(SitemapRound.site_id == site_id)
        count_stmt = count_stmt.where(SitemapRound.site_id == site_id)
    total = db.scalar(count_stmt) or 0
    rows = db.scalars(stmt.order_by(SitemapRound.id.desc()).limit(limit)).all()
    return {"items": [sitemap_sync.serialize_round(row) for row in rows], "total": total}


def list_versions(db: Session, *, source_id: int, limit: int = 20) -> dict:
    source = db.get(SitemapSource, source_id)
    if source is None:
        raise not_found("sitemap_source", source_id)
    rows = db.scalars(
        select(SitemapVersion)
        .where(SitemapVersion.source_id == source_id)
        .order_by(SitemapVersion.id.desc())
        .limit(limit)
    ).all()
    return {
        "source": sitemap_sync.serialize_source(source),
        "items": [
            {
                "id": row.id,
                "status": row.status,
                "content_hash": row.content_hash,
                "entry_count": row.entry_count,
                "error": row.error,
                "round_id": row.round_id,
                "created_at": iso_utc(row.created_at),
            }
            for row in rows
        ],
        "total": len(rows),
    }
