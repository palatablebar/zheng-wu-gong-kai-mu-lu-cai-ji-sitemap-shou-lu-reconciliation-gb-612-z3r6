"""总览：覆盖率、P0/P1/P2、最近巡检、站点覆盖排行、7 天巡检趋势。"""
from __future__ import annotations

from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.config.settings import settings
from src.constants.enums import (
    CRAWL_STATUS_LABELS,
    DEFECT_CATEGORY_LABELS,
    DEFECT_CATEGORY_ORDER,
    DEFECT_SEVERITY_LABELS,
    DEFECT_SEVERITY_ORDER,
    DEFECT_STATUS_LABELS,
    DEFECT_STATUS_ORDER,
)
from src.models.catalog_item import CatalogItem
from src.models.crawl_run import CrawlRun
from src.models.defect import Defect
from src.models.site import Site
from src.models.sitemap_entry import SitemapEntry
from src.utils.timeutil import iso_utc, local_now, utcnow


def worker_alive() -> bool:
    try:
        import time

        import redis

        client = redis.Redis.from_url(settings.redis_url, decode_responses=True, socket_connect_timeout=2)
        value = client.get(f"{settings.app_name}:worker:heartbeat")
        return bool(value) and (time.time() - float(value)) < 120
    except Exception:
        return False


def _ordered_counts(rows, order, labels) -> list[dict]:
    counted = {str(key): int(value) for key, value in rows}
    items = [{"key": key, "label": labels.get(key, key), "count": counted.get(key, 0)} for key in order]
    extras = [
        {"key": key, "label": labels.get(key, key), "count": value}
        for key, value in sorted(counted.items())
        if key not in order
    ]
    return items + extras


def overview(db: Session) -> dict:
    sites_total = db.scalar(select(func.count()).select_from(Site)) or 0
    sites_enabled = db.scalar(select(func.count()).select_from(Site).where(Site.enabled.is_(True))) or 0
    catalog_total = db.scalar(select(func.count()).select_from(CatalogItem)) or 0
    sitemap_total = db.scalar(select(func.count()).select_from(SitemapEntry)) or 0
    runs_total = db.scalar(select(func.count()).select_from(CrawlRun)) or 0
    defects_total = db.scalar(select(func.count()).select_from(Defect)) or 0

    latest = db.scalar(select(CrawlRun).order_by(CrawlRun.id.desc()).limit(1))
    latest_run = None
    if latest is not None:
        site_name = "全部站点"
        if latest.site_id:
            site = db.get(Site, latest.site_id)
            site_name = site.name if site else None
        latest_run = {
            "id": latest.id,
            "run_no": latest.run_no,
            "site_name": site_name,
            "status": latest.status,
            "status_label": CRAWL_STATUS_LABELS.get(latest.status, latest.status),
            "started_at": iso_utc(latest.started_at),
            "coverage": latest.coverage,
            "pages": latest.pages,
            "links": latest.links,
            "unique_links": latest.unique_links,
            "dup_ratio": latest.dup_ratio,
            "defect_count": latest.defect_count,
            "p0_count": latest.p0_count,
            "p1_count": latest.p1_count,
            "p2_count": latest.p2_count,
        }

    severity_rows = db.execute(select(Defect.severity, func.count()).group_by(Defect.severity)).all()
    status_rows = db.execute(select(Defect.status, func.count()).group_by(Defect.status)).all()
    category_rows = db.execute(select(Defect.category, func.count()).group_by(Defect.category)).all()

    site_rows = db.execute(
        select(Defect.site_id, Defect.severity, func.count()).group_by(Defect.site_id, Defect.severity)
    ).all()
    sites = db.scalars(select(Site).order_by(Site.id)).all()
    per_site_severity: dict[int, dict[str, int]] = {}
    for site_id, severity, count in site_rows:
        per_site_severity.setdefault(int(site_id), {})[str(severity)] = int(count)
    coverage_by_site = []
    if latest is not None and (latest.metrics or {}).get("sites"):
        coverage_by_site = [
            {
                "site_id": item.get("site_id"),
                "code": item.get("code"),
                "name": item.get("name"),
                "coverage": item.get("coverage", 0.0),
                "catalog_total": item.get("catalog_total", 0),
                "sitemap_total": item.get("sitemap_total", 0),
                "defects": item.get("defects", 0),
                "p0": item.get("p0", 0),
                "p1": item.get("p1", 0),
                "p2": item.get("p2", 0),
                "pages": item.get("pages", 0),
                "unique": item.get("unique", 0),
            }
            for item in latest.metrics["sites"]
        ]
    else:
        coverage_by_site = [
            {
                "site_id": site.id,
                "code": site.code,
                "name": site.name,
                "coverage": 0.0,
                "catalog_total": 0,
                "sitemap_total": 0,
                "defects": sum(per_site_severity.get(site.id, {}).values()),
                "p0": per_site_severity.get(site.id, {}).get("p0", 0),
                "p1": per_site_severity.get(site.id, {}).get("p1", 0),
                "p2": per_site_severity.get(site.id, {}).get("p2", 0),
                "pages": 0,
                "unique": 0,
            }
            for site in sites
        ]

    since = utcnow() - timedelta(days=7)
    recent_runs = db.scalars(select(CrawlRun).where(CrawlRun.started_at >= since)).all()
    today = local_now().date()
    trend = []
    for offset in range(6, -1, -1):
        day = today - timedelta(days=offset)
        count = sum(
            1
            for run in recent_runs
            if run.started_at
            and (run.started_at + timedelta(minutes=settings.app_timezone_offset_minutes)).date() == day
        )
        trend.append({"date": day.isoformat(), "runs": count})

    return {
        "sites_total": sites_total,
        "sites_enabled": sites_enabled,
        "catalog_total": catalog_total,
        "sitemap_total": sitemap_total,
        "runs_total": runs_total,
        "defects_total": defects_total,
        "pending_total": db.scalar(select(func.count()).select_from(Defect).where(Defect.status == "pending")) or 0,
        "coverage": latest.coverage if latest else 0.0,
        "unreachable_rate": latest.unreachable_rate if latest else 0.0,
        "p0_total": db.scalar(select(func.count()).select_from(Defect).where(Defect.severity == "p0")) or 0,
        "p1_total": db.scalar(select(func.count()).select_from(Defect).where(Defect.severity == "p1")) or 0,
        "p2_total": db.scalar(select(func.count()).select_from(Defect).where(Defect.severity == "p2")) or 0,
        "worker_alive": worker_alive(),
        "latest_run": latest_run,
        "severity": _ordered_counts(severity_rows, DEFECT_SEVERITY_ORDER, DEFECT_SEVERITY_LABELS),
        "status": _ordered_counts(status_rows, DEFECT_STATUS_ORDER, DEFECT_STATUS_LABELS),
        "category": _ordered_counts(category_rows, DEFECT_CATEGORY_ORDER, DEFECT_CATEGORY_LABELS),
        "coverage_by_site": coverage_by_site,
        "trend": trend,
    }
