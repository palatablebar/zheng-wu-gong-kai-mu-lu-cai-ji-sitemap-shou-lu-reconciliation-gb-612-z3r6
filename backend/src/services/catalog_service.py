"""公开目录条目服务（A 集合）：登记、分页查询、按栏目汇总。"""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.models.catalog_item import CatalogItem
from src.models.site import Site
from src.services.url_normalize import normalize_url
from src.utils.errors import AppError, not_found
from src.utils.timeutil import iso_utc


def serialize(item: CatalogItem, site_name: str | None = None, site_code: str | None = None) -> dict:
    return {
        "id": item.id,
        "site_id": item.site_id,
        "site_name": site_name,
        "site_code": site_code,
        "column_code": item.column_code,
        "column_name": item.column_name,
        "entry_url": item.entry_url,
        "canonical_url": item.canonical_url,
        "page_no": item.page_no,
        "item_no": item.item_no,
        "depth": item.depth,
        "discovered_from": item.discovered_from,
        "title": item.title,
        "enabled": item.enabled,
        "created_at": iso_utc(item.created_at),
    }


def list_items(
    db: Session,
    *,
    site_id: int | None = None,
    column_code: str | None = None,
    q: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> dict:
    stmt = select(CatalogItem)
    count_stmt = select(func.count()).select_from(CatalogItem)
    if site_id:
        stmt = stmt.where(CatalogItem.site_id == site_id)
        count_stmt = count_stmt.where(CatalogItem.site_id == site_id)
    if column_code:
        stmt = stmt.where(CatalogItem.column_code == column_code)
        count_stmt = count_stmt.where(CatalogItem.column_code == column_code)
    if q:
        like = f"%{q.strip()}%"
        clause = CatalogItem.title.ilike(like) | CatalogItem.canonical_url.ilike(like)
        stmt = stmt.where(clause)
        count_stmt = count_stmt.where(clause)
    total = db.scalar(count_stmt) or 0
    rows = db.scalars(stmt.order_by(CatalogItem.site_id, CatalogItem.column_code, CatalogItem.item_no).limit(limit).offset(offset)).all()
    sites = {site.id: site for site in db.scalars(select(Site)).all()}
    return {
        "items": [
            serialize(row, (sites.get(row.site_id).name if sites.get(row.site_id) else None), (sites.get(row.site_id).code if sites.get(row.site_id) else None))
            for row in rows
        ],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


def column_summary(db: Session, site_id: int) -> list[dict]:
    rows = db.execute(
        select(
            CatalogItem.column_code,
            CatalogItem.column_name,
            func.count(),
            func.max(CatalogItem.page_no),
        )
        .where(CatalogItem.site_id == site_id)
        .group_by(CatalogItem.column_code, CatalogItem.column_name)
        .order_by(func.min(CatalogItem.item_no))
    ).all()
    return [
        {
            "column_code": code,
            "column_name": name,
            "entries": int(count),
            "pages": int(pages or 0),
        }
        for code, name, count, pages in rows
    ]


def create_item(db: Session, payload: dict) -> CatalogItem:
    site = db.get(Site, int(payload["site_id"]))
    if site is None:
        raise not_found("site", payload.get("site_id"))
    entry_url = payload["entry_url"].strip()
    exists = db.scalar(select(CatalogItem).where(CatalogItem.site_id == site.id, CatalogItem.entry_url == entry_url))
    if exists is not None:
        raise AppError("CONFLICT", 409, {"entry_url": entry_url})
    canonical = normalize_url(payload.get("canonical_url") or entry_url)
    item = CatalogItem(
        site_id=site.id,
        column_code=payload.get("column_code") or "other",
        column_name=payload.get("column_name") or "其他栏目",
        entry_url=entry_url,
        canonical_url=canonical,
        page_no=int(payload.get("page_no") or 1),
        item_no=int(payload.get("item_no") or 0),
        depth=int(payload.get("depth") or 2),
        discovered_from=payload.get("discovered_from") or "rel_next",
        title=payload.get("title") or "",
        enabled=payload.get("enabled", True),
    )
    db.add(item)
    db.flush()
    return item
