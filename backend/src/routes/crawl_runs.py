from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from src.config.database import get_db
from src.constants.roles import CRAWL_CREATE_ROLES
from src.controllers import crawl_run_controller
from src.middlewares.rbac import READ_ROLES, require_roles
from src.schemas.crawl_run import CrawlRunIn
from src.utils.pagination import page_params

router = APIRouter(prefix="/crawl-runs", tags=["crawl-runs"])


@router.get("")
def list_runs(
    site_id: int | None = None,
    status: str | None = None,
    limit: int = Query(20),
    offset: int = Query(0),
    db: Session = Depends(get_db),
    principal: dict = Depends(require_roles(*READ_ROLES)),
) -> dict:
    page = page_params(limit, offset)
    return crawl_run_controller.list_runs(db, site_id=site_id, status=status, limit=page.limit, offset=page.offset)


@router.get("/{run_id}")
def get_run(run_id: int, db: Session = Depends(get_db), principal: dict = Depends(require_roles(*READ_ROLES))) -> dict:
    return crawl_run_controller.get_run(db, run_id)


@router.post("", status_code=201)
def create_run(
    payload: CrawlRunIn,
    request: Request,
    db: Session = Depends(get_db),
    principal: dict = Depends(require_roles(*CRAWL_CREATE_ROLES)),
) -> dict:
    return crawl_run_controller.create_run(db, payload.model_dump(), principal, request)
