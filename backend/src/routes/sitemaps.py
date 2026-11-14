from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from src.config.database import get_db
from src.constants.roles import CATALOG_WRITE_ROLES, SITEMAP_SYNC_ROLES
from src.controllers import sitemap_controller
from src.middlewares.rbac import READ_ROLES, require_roles
from src.schemas.sitemap import FixtureSyncIn, SitemapEntryIn, SitemapSyncIn
from src.services import sitemap_service
from src.utils.pagination import page_params

router = APIRouter(prefix="/sitemaps", tags=["sitemaps"])


@router.get("")
def list_entries(
    site_id: int | None = None,
    q: str | None = None,
    source_file: str | None = None,
    is_gap: bool | None = None,
    limit: int = Query(20),
    offset: int = Query(0),
    db: Session = Depends(get_db),
    principal: dict = Depends(require_roles(*READ_ROLES)),
) -> dict:
    page = page_params(limit, offset)
    return sitemap_service.list_entries(
        db,
        site_id=site_id,
        q=q,
        source_file=source_file,
        is_gap=is_gap,
        limit=page.limit,
        offset=page.offset,
    )


@router.post("", status_code=201)
def create_entry(
    payload: SitemapEntryIn,
    db: Session = Depends(get_db),
    principal: dict = Depends(require_roles(*CATALOG_WRITE_ROLES)),
) -> dict:
    entry = sitemap_service.create_entry(db, payload.model_dump())
    db.commit()
    return sitemap_service.serialize(entry)


@router.get("/sources")
def list_sources(
    site_id: int,
    db: Session = Depends(get_db),
    principal: dict = Depends(require_roles(*READ_ROLES)),
) -> dict:
    return sitemap_service.list_sources(db, site_id=site_id)


@router.get("/sources/{source_id}/versions")
def list_versions(
    source_id: int,
    db: Session = Depends(get_db),
    principal: dict = Depends(require_roles(*READ_ROLES)),
) -> dict:
    return sitemap_service.list_versions(db, source_id=source_id)


@router.get("/rounds")
def list_rounds(
    site_id: int | None = None,
    limit: int = Query(20),
    db: Session = Depends(get_db),
    principal: dict = Depends(require_roles(*READ_ROLES)),
) -> dict:
    return sitemap_service.list_rounds(db, site_id=site_id, limit=limit)


@router.post("/sync", status_code=201)
def sync_payload(
    payload: SitemapSyncIn,
    request: Request,
    db: Session = Depends(get_db),
    principal: dict = Depends(require_roles(*SITEMAP_SYNC_ROLES)),
) -> dict:
    return sitemap_controller.sync_payload(db, payload, principal, request)


@router.post("/sync-fixture", status_code=201)
def sync_fixture(
    payload: FixtureSyncIn,
    request: Request,
    db: Session = Depends(get_db),
    principal: dict = Depends(require_roles(*SITEMAP_SYNC_ROLES)),
) -> dict:
    return sitemap_controller.sync_fixture(db, payload, principal, request)
