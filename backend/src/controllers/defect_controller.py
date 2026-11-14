"""缺陷单控制器：分类查询 + 整改流转。"""
from __future__ import annotations

from fastapi import Request
from sqlalchemy.orm import Session

from src.services import audit_service, defect_service


def list_defects(db: Session, **filters) -> dict:
    return defect_service.list_defects(db, **filters)


def facets(db: Session, run_id: int | None = None) -> dict:
    return defect_service.facets(db, run_id)


def get_defect(db: Session, defect_id: int) -> dict:
    return defect_service.serialize(defect_service.get_defect(db, defect_id))


def review(db: Session, defect_id: int, payload: dict, principal: dict, request: Request) -> dict:
    defect = defect_service.get_defect(db, defect_id)
    defect_service.review(
        db,
        defect,
        status=payload["status"],
        note=payload.get("note"),
        reviewer=principal["email"],
    )
    audit_service.record(
        db,
        actor_email=principal["email"],
        actor_role=principal["role"],
        action="defect.review",
        entity="defect",
        entity_id=defect.id,
        detail={"status": defect.status, "category": defect.category, "severity": defect.severity},
        ip=request.client.host if request.client else None,
    )
    db.commit()
    return defect_service.serialize(defect)
