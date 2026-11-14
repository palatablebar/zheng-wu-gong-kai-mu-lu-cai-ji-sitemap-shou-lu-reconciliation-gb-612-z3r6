from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from src.config.database import get_db
from src.constants.roles import AUDIT_ROLES
from src.middlewares.rbac import require_roles
from src.services import audit_service

router = APIRouter(tags=["audit"])


@router.get("/audit")
def audit_logs(
    limit: int = Query(80, ge=1, le=200),
    action: str | None = None,
    db: Session = Depends(get_db),
    principal: dict = Depends(require_roles(*AUDIT_ROLES)),
) -> dict:
    return audit_service.list_logs(db, limit=limit, action=action)
