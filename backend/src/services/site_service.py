"""站点（政务站）服务：登记、查询、序列化。"""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.constants.demo_data import ORG
from src.models.catalog_item import CatalogItem
from src.models.site import Site
from src.models.sitemap_entry import SitemapEntry
from src.utils.errors import AppError, not_found
from src.utils.timeutil import iso_utc


def serialize(site: Site, *, catalog_count: int | None = None, sitemap_count: int | None = None, coverage: float | None = None) -> dict:
    return {
        "id": site.id,
        "code": site.code,
        "name": site.name,
        "home_url": site.home_url,
        "sitemap_url": site.sitemap_url,
        "dept": site.dept,
        "region": site.region,
        "page_size": site.page_size,
        "max_depth": site.max_depth,
        "note": site.note,
        "config": site.config or {},
        "enabled": site.enabled,
        "catalog_count": catalog_count,
        "sitemap_count": sitemap_count,
        "coverage": coverage,
        "last_crawled_at": iso_utc(site.last_crawled_at),
        "created_at": iso_utc(site.created_at),
    }


def _counts(db: Session, site_ids: list[int]) -> tuple[dict[int, int], dict[int, int]]:
    catalog: dict[int, int] = {}
    sitemap: dict[int, int] = {}
    if not site_ids:
        return catalog, sitemap
    for site_id, count in db.execute(
        select(CatalogItem.site_id, func.count()).where(CatalogItem.site_id.in_(site_ids)).group_by(CatalogItem.site_id)
    ).all():
        catalog[int(site_id)] = int(count)
    for site_id, count in db.execute(
        select(SitemapEntry.site_id, func.count()).where(SitemapEntry.site_id.in_(site_ids)).group_by(SitemapEntry.site_id)
    ).all():
        sitemap[int(site_id)] = int(count)
    return catalog, sitemap


def list_sites(
    db: Session,
    *,
    q: str | None = None,
    region: str | None = None,
    enabled: bool | None = None,
    limit: int = 20,
    offset: int = 0,
) -> dict:
    stmt = select(Site)
    count_stmt = select(func.count()).select_from(Site)
    if q:
        like = f"%{q.strip()}%"
        clause = Site.name.ilike(like) | Site.code.ilike(like) | Site.home_url.ilike(like)
        stmt = stmt.where(clause)
        count_stmt = count_stmt.where(clause)
    if region:
        stmt = stmt.where(Site.region == region)
        count_stmt = count_stmt.where(Site.region == region)
    if enabled is not None:
        stmt = stmt.where(Site.enabled == enabled)
        count_stmt = count_stmt.where(Site.enabled == enabled)
    total = db.scalar(count_stmt) or 0
    rows = db.scalars(stmt.order_by(Site.id).limit(limit).offset(offset)).all()
    catalog_counts, sitemap_counts = _counts(db, [row.id for row in rows])
    return {
        "items": [
            serialize(row, catalog_count=catalog_counts.get(row.id, 0), sitemap_count=sitemap_counts.get(row.id, 0))
            for row in rows
        ],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


def get_site(db: Session, site_id: int) -> Site:
    site = db.get(Site, site_id)
    if site is None:
        raise not_found("site", site_id)
    return site


def create_site(db: Session, payload: dict) -> Site:
    exists = db.scalar(select(Site).where(Site.code == payload["code"]))
    if exists is not None:
        raise AppError("CONFLICT", 409, {"code": payload["code"]})
    site = Site(
        code=payload["code"],
        name=payload["name"],
        home_url=(payload.get("home_url") or "").rstrip("/"),
        sitemap_url=payload.get("sitemap_url") or "",
        dept=payload.get("dept") or ORG,
        region=payload.get("region") or "市本级",
        page_size=int(payload.get("page_size") or 12),
        max_depth=int(payload.get("max_depth") or 3),
        note=payload.get("note"),
        config=payload.get("config") or {},
        enabled=payload.get("enabled", True),
    )
    db.add(site)
    db.flush()
    return site


def update_site(db: Session, site: Site, payload: dict) -> Site:
    for field in ("name", "home_url", "sitemap_url", "dept", "region", "page_size", "max_depth", "note", "config", "enabled"):
        if field in payload and payload[field] is not None:
            setattr(site, field, payload[field])
    db.flush()
    return site
