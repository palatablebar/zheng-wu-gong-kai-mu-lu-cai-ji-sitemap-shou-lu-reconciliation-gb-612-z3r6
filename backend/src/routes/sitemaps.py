from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from src.config.database import get_db
from src.constants.roles import CATALOG_WRITE_ROLES
from src.middlewares.rbac import READ_ROLES, require_roles
from src.schemas.sitemap import SitemapEntryIn
from src.services import sitemap_service
from src.utils.pagination import page_params

router = APIRouter(prefix="/sitemaps", tags=["sitemaps"])


@router.get("")
def list_entries(
    site_id: int | None = None,
    q: str | None = None,
    limit: int = Query(20),
    offset: int = Query(0),
    db: Session = Depends(get_db),
    principal: dict = Depends(require_roles(*READ_ROLES)),
) -> dict:
    page = page_params(limit, offset)
    return sitemap_service.list_entries(db, site_id=site_id, q=q, limit=page.limit, offset=page.offset)


@router.post("", status_code=201)
def create_entry(
    payload: SitemapEntryIn,
    db: Session = Depends(get_db),
    principal: dict = Depends(require_roles(*CATALOG_WRITE_ROLES)),
) -> dict:
    entry = sitemap_service.create_entry(db, payload.model_dump())
    db.commit()
    return sitemap_service.serialize(entry)
