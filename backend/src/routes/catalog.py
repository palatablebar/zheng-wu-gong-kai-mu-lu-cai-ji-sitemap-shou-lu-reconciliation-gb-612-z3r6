from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from src.config.database import get_db
from src.constants.roles import CATALOG_WRITE_ROLES
from src.controllers import catalog_controller
from src.middlewares.rbac import READ_ROLES, require_roles
from src.schemas.catalog import CatalogItemIn
from src.utils.pagination import page_params

router = APIRouter(prefix="/catalog", tags=["catalog"])


@router.get("")
def list_items(
    site_id: int | None = None,
    column_code: str | None = None,
    q: str | None = None,
    limit: int = Query(20),
    offset: int = Query(0),
    db: Session = Depends(get_db),
    principal: dict = Depends(require_roles(*READ_ROLES)),
) -> dict:
    page = page_params(limit, offset)
    return catalog_controller.list_items(db, site_id=site_id, column_code=column_code, q=q, limit=page.limit, offset=page.offset)


@router.get("/normalize")
def normalize_preview(
    url: str = Query(min_length=1, max_length=400),
    base: str | None = Query(default=None, max_length=400),
    principal: dict = Depends(require_roles(*READ_ROLES)),
) -> dict:
    return catalog_controller.preview_normalize(url, base)


@router.post("", status_code=201)
def create_item(
    payload: CatalogItemIn,
    request: Request,
    db: Session = Depends(get_db),
    principal: dict = Depends(require_roles(*CATALOG_WRITE_ROLES)),
) -> dict:
    return catalog_controller.create_item(db, payload.model_dump(), principal, request)
