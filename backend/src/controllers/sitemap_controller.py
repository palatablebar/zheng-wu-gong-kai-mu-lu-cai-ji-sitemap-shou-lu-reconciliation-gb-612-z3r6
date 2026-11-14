"""sitemap 子清单同步控制器：手工/演示同步 + 审计留痕。"""
from __future__ import annotations

from fastapi import Request
from sqlalchemy.orm import Session

from src.constants.demo_data import SITES
from src.models.site import Site
from src.schemas.sitemap import FixtureSyncIn, SitemapSyncIn
from src.services import audit_service, sitemap_service, sitemap_sync
from src.utils.errors import AppError, not_found

SPEC_BY_CODE = {spec["code"]: spec for spec in SITES}


def sync_payload(db: Session, payload: SitemapSyncIn, principal: dict, request: Request) -> dict:
    site = db.get(Site, int(payload.site_id))
    if site is None:
        raise not_found("site", payload.site_id)
    sources = [item.model_dump() for item in payload.sources]
    round_row = sitemap_sync.sync_from_payload(
        db, site, sources, triggered_by=principal.get("email") or "manual"
    )
    audit_service.record(
        db,
        actor_email=principal["email"],
        actor_role=principal["role"],
        action="sitemap.sync",
        entity="sitemap_round",
        entity_id=round_row.id,
        detail={
            "site_id": site.id,
            "round_no": round_row.round_no,
            "status": round_row.status,
            "gap_count": round_row.gap_count,
            "stats": round_row.stats,
        },
        ip=request.client.host if request.client else None,
    )
    db.commit()
    return sitemap_service.list_rounds(db, site_id=site.id, limit=1)["items"][0]


def sync_fixture(db: Session, payload: FixtureSyncIn, principal: dict, request: Request) -> dict:
    """从离线 fixture 重新拉取子清单（演示/测试用），支持注入超时失败。"""
    target_id = payload.site_id
    fail_sources = set(payload.fail_sources or [])
    if target_id:
        sites = [db.get(Site, int(target_id))]
        if sites[0] is None:
            raise not_found("site", target_id)
    else:
        from sqlalchemy import select

        sites = db.scalars(select(Site).order_by(Site.id)).all()
    rounds = []
    for site in sites:
        spec = SPEC_BY_CODE.get(site.code)
        if spec is None:
            raise AppError("VALIDATION", 400, {"site_code": site.code, "reason": "该站点没有离线 fixture"})
        round_row = sitemap_sync.sync_fixture_site(
            db,
            site,
            spec,
            fail_sources=fail_sources,
            triggered_by=principal.get("email") or "manual",
        )
        rounds.append(round_row)
        audit_service.record(
            db,
            actor_email=principal["email"],
            actor_role=principal["role"],
            action="sitemap.sync",
            entity="sitemap_round",
            entity_id=round_row.id,
            detail={
                "site_id": site.id,
                "round_no": round_row.round_no,
                "status": round_row.status,
                "fail_sources": sorted(fail_sources),
                "gap_count": round_row.gap_count,
            },
            ip=request.client.host if request.client else None,
        )
    db.commit()
    return {
        "items": [sitemap_service.list_rounds(db, site_id=site.id, limit=1)["items"][0] for site in sites],
        "total": len(rounds),
    }
