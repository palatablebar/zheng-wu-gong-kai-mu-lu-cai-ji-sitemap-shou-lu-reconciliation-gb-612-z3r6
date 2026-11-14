from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from src.config.database import get_db
from src.constants.roles import DEFECT_REVIEW_ROLES
from src.controllers import defect_controller
from src.middlewares.rbac import READ_ROLES, require_roles
from src.schemas.crawl_run import DefectReviewIn
from src.utils.pagination import page_params

router = APIRouter(prefix="/defects", tags=["defects"])


@router.get("")
def list_defects(
    run_id: int | None = None,
    site_id: int | None = None,
    category: str | None = None,
    severity: str | None = None,
    status: str | None = None,
    q: str | None = None,
    limit: int = Query(20),
    offset: int = Query(0),
    db: Session = Depends(get_db),
    principal: dict = Depends(require_roles(*READ_ROLES)),
) -> dict:
    page = page_params(limit, offset)
    return defect_controller.list_defects(
        db,
        run_id=run_id,
        site_id=site_id,
        category=category,
        severity=severity,
        status=status,
        q=q,
        limit=page.limit,
        offset=page.offset,
    )


@router.get("/facets")
def facets(
    run_id: int | None = None,
    db: Session = Depends(get_db),
    principal: dict = Depends(require_roles(*READ_ROLES)),
) -> dict:
    return defect_controller.facets(db, run_id)


@router.get("/{defect_id}")
def get_defect(defect_id: int, db: Session = Depends(get_db), principal: dict = Depends(require_roles(*READ_ROLES))) -> dict:
    return defect_controller.get_defect(db, defect_id)


@router.patch("/{defect_id}/review")
def review(
    defect_id: int,
    payload: DefectReviewIn,
    request: Request,
    db: Session = Depends(get_db),
    principal: dict = Depends(require_roles(*DEFECT_REVIEW_ROLES)),
) -> dict:
    return defect_controller.review(db, defect_id, payload.model_dump(), principal, request)
