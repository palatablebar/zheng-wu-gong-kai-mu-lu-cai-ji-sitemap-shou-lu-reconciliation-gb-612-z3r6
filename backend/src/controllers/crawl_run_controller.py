"""巡检运行控制器：发起巡检 + 审计留痕。"""
from __future__ import annotations

from fastapi import Request
from sqlalchemy.orm import Session

from src.services import audit_service, crawl_run_service


def list_runs(db: Session, **filters) -> dict:
    return crawl_run_service.list_runs(db, **filters)


def get_run(db: Session, run_id: int) -> dict:
    return crawl_run_service.serialize(crawl_run_service.get_run(db, run_id))


def create_run(db: Session, payload: dict, principal: dict, request: Request) -> dict:
    run = crawl_run_service.create_and_execute(
        db,
        site_id=payload.get("site_id"),
        trigger=payload.get("trigger") or "manual",
        operator_email=principal["email"],
    )
    audit_service.record(
        db,
        actor_email=principal["email"],
        actor_role=principal["role"],
        action="crawl.create",
        entity="crawl_run",
        entity_id=run.id,
        detail={
            "run_no": run.run_no,
            "status": run.status,
            "pages": run.pages,
            "unique": run.unique_links,
            "defects": run.defect_count,
        },
        ip=request.client.host if request.client else None,
    )
    audit_service.record(
        db,
        actor_email=principal["email"],
        actor_role=principal["role"],
        action="crawl.complete",
        entity="crawl_run",
        entity_id=run.id,
        detail={
            "coverage": run.coverage,
            "p0": run.p0_count,
            "p1": run.p1_count,
            "p2": run.p2_count,
        },
        layer="domain",
        ip=request.client.host if request.client else None,
    )
    db.commit()
    return crawl_run_service.serialize(run)
