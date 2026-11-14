"""站点控制器：登记 / 修改 / 详情。"""
from __future__ import annotations

from fastapi import Request
from sqlalchemy.orm import Session

from src.services import audit_service, catalog_service, site_service


def list_sites(db: Session, **filters) -> dict:
    return site_service.list_sites(db, **filters)


def get_site(db: Session, site_id: int) -> dict:
    site = site_service.get_site(db, site_id)
    data = site_service.serialize(site)
    data["columns"] = catalog_service.column_summary(db, site.id)
    return data


def create_site(db: Session, payload: dict, principal: dict, request: Request) -> dict:
    site = site_service.create_site(db, payload)
    audit_service.record(
        db,
        actor_email=principal["email"],
        actor_role=principal["role"],
        action="site.create",
        entity="site",
        entity_id=site.id,
        detail={"code": site.code, "name": site.name, "home_url": site.home_url},
        ip=request.client.host if request.client else None,
    )
    db.commit()
    return site_service.serialize(site)


def update_site(db: Session, site_id: int, payload: dict, principal: dict, request: Request) -> dict:
    site = site_service.get_site(db, site_id)
    site_service.update_site(db, site, payload)
    audit_service.record(
        db,
        actor_email=principal["email"],
        actor_role=principal["role"],
        action="site.update",
        entity="site",
        entity_id=site.id,
        detail={"fields": sorted(payload.keys())},
        ip=request.client.host if request.client else None,
    )
    db.commit()
    return site_service.serialize(site)
