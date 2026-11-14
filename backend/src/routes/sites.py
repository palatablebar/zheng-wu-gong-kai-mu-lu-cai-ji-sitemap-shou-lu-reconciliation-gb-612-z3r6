from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from src.config.database import get_db
from src.constants.roles import SITE_WRITE_ROLES
from src.controllers import site_controller
from src.middlewares.rbac import READ_ROLES, require_roles
from src.schemas.site import SiteIn, SitePatch
from src.utils.pagination import page_params

router = APIRouter(prefix="/sites", tags=["sites"])


@router.get("")
def list_sites(
    q: str | None = None,
    region: str | None = None,
    enabled: bool | None = None,
    limit: int = Query(20),
    offset: int = Query(0),
    db: Session = Depends(get_db),
    principal: dict = Depends(require_roles(*READ_ROLES)),
) -> dict:
    page = page_params(limit, offset)
    return site_controller.list_sites(db, q=q, region=region, enabled=enabled, limit=page.limit, offset=page.offset)


@router.get("/{site_id}")
def get_site(site_id: int, db: Session = Depends(get_db), principal: dict = Depends(require_roles(*READ_ROLES))) -> dict:
    return site_controller.get_site(db, site_id)


@router.post("", status_code=201)
def create_site(
    payload: SiteIn,
    request: Request,
    db: Session = Depends(get_db),
    principal: dict = Depends(require_roles(*SITE_WRITE_ROLES)),
) -> dict:
    return site_controller.create_site(db, payload.model_dump(), principal, request)


@router.patch("/{site_id}")
def update_site(
    site_id: int,
    payload: SitePatch,
    request: Request,
    db: Session = Depends(get_db),
    principal: dict = Depends(require_roles(*SITE_WRITE_ROLES)),
) -> dict:
    return site_controller.update_site(db, site_id, payload.model_dump(exclude_unset=True), principal, request)
