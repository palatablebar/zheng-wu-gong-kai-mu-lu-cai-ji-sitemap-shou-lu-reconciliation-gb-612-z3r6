"""巡检运行服务：编排算法 A（分页抓取）+ 算法 B（三向对账），落库缺陷单。

一次巡检处理「一个站点」或「全部启用站点」。所有计算在后端完成，
前端只消费 /api/crawl-runs 与 /api/defects 的结果。
"""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.constants.demo_data import SITES as SITE_SPECS
from src.constants.enums import CRAWL_STATUS_LABELS, TRIGGER_LABELS, CrawlStatus
from src.constants.limits import MAX_CRAWL_DEPTH, MAX_CRAWL_PAGES
from src.models.catalog_item import CatalogItem
from src.models.crawl_run import CrawlRun
from src.models.defect import Defect
from src.models.site import Site
from src.models.sitemap_entry import SitemapEntry
from src.services import crawl_engine, fixture_site, reconcile_engine
from src.services.url_normalize import normalize_url
from src.utils.errors import AppError
from src.utils.timeutil import iso_utc, local_now, utcnow

SPEC_BY_CODE = {spec["code"]: spec for spec in SITE_SPECS}


def serialize(run: CrawlRun, site_name: str | None = None) -> dict:
    return {
        "id": run.id,
        "run_no": run.run_no,
        "site_id": run.site_id,
        "site_name": site_name,
        "trigger": run.trigger,
        "trigger_label": TRIGGER_LABELS.get(run.trigger, run.trigger),
        "status": run.status,
        "status_label": CRAWL_STATUS_LABELS.get(run.status, run.status),
        "operator_email": run.operator_email,
        "pages": run.pages,
        "links": run.links,
        "unique_links": run.unique_links,
        "dup_ratio": run.dup_ratio,
        "depth_max": run.depth_max,
        "sitemap_count": run.sitemap_count,
        "catalog_count": run.catalog_count,
        "coverage": run.coverage,
        "unreachable_rate": run.unreachable_rate,
        "defect_count": run.defect_count,
        "p0_count": run.p0_count,
        "p1_count": run.p1_count,
        "p2_count": run.p2_count,
        "metrics": run.metrics or {},
        "log_text": run.log_text,
        "started_at": iso_utc(run.started_at),
        "finished_at": iso_utc(run.finished_at),
    }


def next_run_no(db: Session) -> str:
    prefix = f"C{local_now():%Y%m%d}"
    count = db.scalar(select(func.count()).select_from(CrawlRun).where(CrawlRun.run_no.like(f"{prefix}%"))) or 0
    return f"{prefix}-{count + 1:04d}"


def _catalog_payload(db: Session, site_id: int) -> list[dict]:
    rows = db.scalars(select(CatalogItem).where(CatalogItem.site_id == site_id)).all()
    return [
        {
            "entry_url": row.entry_url,
            "canonical_url": row.canonical_url,
            "column_name": row.column_name,
            "column_code": row.column_code,
            "page_no": row.page_no,
            "title": row.title,
        }
        for row in rows
    ]


def _sitemap_payload(db: Session, site_id: int) -> list[dict]:
    rows = db.scalars(select(SitemapEntry).where(SitemapEntry.site_id == site_id)).all()
    return [
        {
            "loc": row.loc,
            "canonical_url": row.canonical_url,
            "lastmod": row.lastmod,
            "source_file": row.source_file,
        }
        for row in rows
    ]


def _upsert_defects(db: Session, run: CrawlRun, site: Site, defects: list[dict]) -> None:
    for item in defects:
        existing = db.scalar(select(Defect).where(Defect.run_id == run.id, Defect.fingerprint == item["fingerprint"]))
        if existing is None:
            db.add(
                Defect(
                    run_id=run.id,
                    site_id=site.id,
                    site_code=item["site_code"],
                    category=item["category"],
                    severity=item["severity"],
                    fingerprint=item["fingerprint"],
                    url=item["url"],
                    canonical_url=item["canonical_url"],
                    column_name=item["column_name"],
                    title=item["title"],
                    summary=item["summary"],
                    evidence=item["evidence"],
                )
            )
        else:
            # 已存在的缺陷只刷新描述与证据，不覆盖人工整改状态（status/reviewer/review_note）
            existing.url = item["url"]
            existing.canonical_url = item["canonical_url"]
            existing.column_name = item["column_name"]
            existing.title = item["title"]
            existing.summary = item["summary"]
            existing.severity = item["severity"]
            existing.evidence = item["evidence"]


def _site_metrics(site: Site, crawl: dict, result: dict) -> dict:
    stats = result["stats"]
    crawl_stats = crawl["stats"]
    return {
        "site_id": site.id,
        "code": site.code,
        "name": site.name,
        "pages": crawl_stats["pages"],
        "links": crawl_stats["links"],
        "unique": crawl_stats["unique"],
        "dup_ratio": crawl_stats["dup_ratio"],
        "depth_max": crawl_stats["depth_max"],
        "columns": crawl_stats["columns"],
        "catalog_total": stats["catalog_total"],
        "sitemap_total": stats["sitemap_total"],
        "reachable": stats["reachable"],
        "hit": stats["hit"],
        "coverage": stats["coverage"],
        "unreachable_rate": stats["unreachable_rate"],
        "dead": stats["dead"],
        "defects": len(result["defects"]),
        "p0": stats["p0"],
        "p1": stats["p1"],
        "p2": stats["p2"],
        "by_category": stats["by_category"],
        "skipped": len(crawl["skipped"]),
    }


def execute_run(db: Session, run: CrawlRun, sites: list[Site]) -> CrawlRun:
    run.status = CrawlStatus.RUNNING.value
    try:
        totals = {
            "pages": 0,
            "links": 0,
            "unique": 0,
            "catalog_total": 0,
            "sitemap_total": 0,
            "hit": 0,
            "dead": 0,
            "defects": 0,
            "p0": 0,
            "p1": 0,
            "p2": 0,
            "skipped": 0,
        }
        by_category: dict[str, int] = {}
        per_site: list[dict] = []
        for site in sites:
            spec = SPEC_BY_CODE.get(site.code)
            root = fixture_site.fixture_root(site.code)
            if spec is not None:
                fixture_site.ensure_site_fixture(spec)
            crawl = crawl_engine.crawl_site(
                home_url=site.home_url,
                fixture_root=root,
                page_size=site.page_size,
                max_depth=min(site.max_depth or 3, MAX_CRAWL_DEPTH),
                max_pages=MAX_CRAWL_PAGES,
            )
            sitemap_rows = _sitemap_payload(db, site.id)
            probes = dict(crawl["probes"])
            extra = [row["canonical_url"] for row in sitemap_rows if normalize_url(row["canonical_url"]) not in probes]
            if extra:
                probes.update(crawl_engine.probe_urls(root, extra))
            result = reconcile_engine.reconcile(
                site_code=site.code,
                catalog_items=_catalog_payload(db, site.id),
                sitemap_locs=sitemap_rows,
                probes=probes,
            )
            _upsert_defects(db, run, site, result["defects"])
            metrics = _site_metrics(site, crawl, result)
            per_site.append(metrics)
            for key in totals:
                totals[key] += int(metrics.get(key, 0) or 0)
            for key, value in (metrics.get("by_category") or {}).items():
                by_category[key] = by_category.get(key, 0) + int(value)
            site.last_crawled_at = utcnow()

        catalog_total = totals["catalog_total"] or 0
        coverage = round(totals["hit"] / catalog_total, 4) if catalog_total else 0.0
        unreachable_rate = round(
            (totals["catalog_total"] - sum(item["reachable"] for item in per_site)) / catalog_total, 4
        ) if catalog_total else 0.0
        dup_ratio = round(1 - (totals["unique"] / totals["links"]), 4) if totals["links"] else 0.0

        run.pages = totals["pages"]
        run.links = totals["links"]
        run.unique_links = totals["unique"]
        run.dup_ratio = dup_ratio
        run.depth_max = max((int(item["depth_max"]) for item in per_site), default=0)
        run.sitemap_count = totals["sitemap_total"]
        run.catalog_count = totals["catalog_total"]
        run.coverage = coverage
        run.unreachable_rate = unreachable_rate
        run.defect_count = sum(int(item["defects"]) for item in per_site)
        run.p0_count = totals["p0"]
        run.p1_count = totals["p1"]
        run.p2_count = totals["p2"]
        run.metrics = {
            "totals": {
                "pages": totals["pages"],
                "links": totals["links"],
                "unique": totals["unique"],
                "catalog_total": totals["catalog_total"],
                "sitemap_total": totals["sitemap_total"],
                "hit": totals["hit"],
                "dead": totals["dead"],
                "coverage": coverage,
                "unreachable_rate": unreachable_rate,
                "dup_ratio": dup_ratio,
                "skipped": totals["skipped"],
            },
            "by_category": by_category,
            "sites": per_site,
            "sites_crawled": [site.code for site in sites],
        }
        run.log_text = "\n".join(
            [
                f"巡检 {run.run_no}：{len(sites)} 个站点、{totals['pages']} 个分页清单页",
                f"抓取链接 {totals['links']} 条，canonical 去重后 {totals['unique']} 条（重复率 {dup_ratio:.2%}）",
                f"目录条目 {totals['catalog_total']} 条、sitemap loc {totals['sitemap_total']} 条",
                f"三向命中 {totals['hit']} 条 → 覆盖率 {coverage:.2%}，不可达率 {unreachable_rate:.2%}",
                f"检出缺陷 {run.defect_count} 条：P0 {totals['p0']} / P1 {totals['p1']} / P2 {totals['p2']}",
                "分类：" + "、".join(f"{key}={value}" for key, value in sorted(by_category.items())),
            ]
        )
        run.status = CrawlStatus.SUCCESS.value if sites else CrawlStatus.PARTIAL.value
    except Exception as exc:  # noqa: BLE001 - 运行失败留痕，不抛 500
        run.status = CrawlStatus.FAILED.value
        run.log_text = f"巡检失败：{exc}"
        run.metrics = {"error": str(exc)[:300]}
    run.finished_at = utcnow()
    db.flush()
    return run


def create_and_execute(
    db: Session,
    *,
    site_id: int | None,
    trigger: str,
    operator_email: str,
    seed_key: str | None = None,
) -> CrawlRun:
    if seed_key:
        existing = db.scalar(select(CrawlRun).where(CrawlRun.seed_key == seed_key))
        if existing is not None:
            return existing
    if site_id:
        site = db.get(Site, site_id)
        if site is None:
            raise AppError("NOT_FOUND", 404, {"entity": "site", "id": site_id})
        sites = [site]
    else:
        sites = db.scalars(select(Site).where(Site.enabled.is_(True)).order_by(Site.id)).all()
    run = CrawlRun(
        run_no=next_run_no(db),
        site_id=site_id,
        trigger=trigger,
        status=CrawlStatus.RUNNING.value,
        operator_email=operator_email,
        seed_key=seed_key,
    )
    db.add(run)
    db.flush()
    return execute_run(db, run, list(sites))


def list_runs(
    db: Session,
    *,
    site_id: int | None = None,
    status: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> dict:
    stmt = select(CrawlRun)
    count_stmt = select(func.count()).select_from(CrawlRun)
    if site_id:
        stmt = stmt.where(CrawlRun.site_id == site_id)
        count_stmt = count_stmt.where(CrawlRun.site_id == site_id)
    if status:
        stmt = stmt.where(CrawlRun.status == status)
        count_stmt = count_stmt.where(CrawlRun.status == status)
    total = db.scalar(count_stmt) or 0
    rows = db.scalars(stmt.order_by(CrawlRun.id.desc()).limit(limit).offset(offset)).all()
    names = {site.id: site.name for site in db.scalars(select(Site)).all()}
    return {
        "items": [serialize(row, names.get(row.site_id) if row.site_id else "全部站点") for row in rows],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


def get_run(db: Session, run_id: int) -> CrawlRun:
    run = db.get(CrawlRun, run_id)
    if run is None:
        raise AppError("NOT_FOUND", 404, {"entity": "crawl_run", "id": run_id})
    return run
