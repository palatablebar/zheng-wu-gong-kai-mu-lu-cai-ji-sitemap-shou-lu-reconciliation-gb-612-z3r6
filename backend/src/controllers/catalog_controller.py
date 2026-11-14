"""目录条目控制器（A 集合登记）。"""
from __future__ import annotations

from fastapi import Request
from sqlalchemy.orm import Session

from src.services import audit_service, catalog_service
from src.services.url_normalize import normalize_url


def list_items(db: Session, **filters) -> dict:
    return catalog_service.list_items(db, **filters)


def create_item(db: Session, payload: dict, principal: dict, request: Request) -> dict:
    item = catalog_service.create_item(db, payload)
    audit_service.record(
        db,
        actor_email=principal["email"],
        actor_role=principal["role"],
        action="catalog.create",
        entity="catalog_item",
        entity_id=item.id,
        detail={"site_id": item.site_id, "canonical": item.canonical_url},
        ip=request.client.host if request.client else None,
    )
    db.commit()
    return catalog_service.serialize(item)


def preview_normalize(url: str, base: str | None = None) -> dict:
    """URL 规范化口径的在线预览（前端「口径核对」按钮用，只读）。"""
    canonical = normalize_url(url, base=base)
    return {"input": url, "base": base, "canonical": canonical, "changed": canonical != (url or "").strip()}
