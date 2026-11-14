"""幂等 seed：3 账号 / 3 站点 / 360 条目录 / 362 条 sitemap loc / 1 次巡检 / 31 条缺陷。

自然键 upsert：
  users.email
  sites.code
  catalog_items(site_id, entry_url)
  sitemap_entries(site_id, loc)
  crawl_runs.seed_key
  defects(run_id, fingerprint)
  audit_logs.seed_key

重复执行不新增、不覆盖人工整改状态；SEED_SUMMARY 一行逐字一致。
数量口径：sources=站点数、runs=巡检次数、findings=缺陷单数、pending=待整改缺陷数。
"""
from __future__ import annotations

from sqlalchemy import func, select

from src.config.database import session_scope
from src.models.audit import AuditLog
from src.models.catalog_item import CatalogItem
from src.models.crawl_run import CrawlRun
from src.models.defect import Defect
from src.models.site import Site
from src.models.sitemap_entry import SitemapEntry
from src.models.user import User
from src.services import crawl_run_service, fixture_site, site_service
from src.utils.logger import get_logger
from src.utils.security import hash_password

from scripts.demo_config import (
    DEMO_PASSWORD,
    DEMO_USERS,
    ORG,
    SEED_RUN_KEY,
    SEED_RUN_OPERATOR,
    SITES,
)

logger = get_logger("seed")


def ensure_users(db) -> int:
    for email, display_name, role in DEMO_USERS:
        user = db.scalar(select(User).where(User.email == email))
        if user is None:
            db.add(
                User(
                    email=email,
                    password_hash=hash_password(DEMO_PASSWORD),
                    display_name=display_name,
                    role=role,
                    org=ORG,
                )
            )
    db.flush()
    return db.scalar(select(func.count()).select_from(User)) or 0


def ensure_sites(db) -> dict[str, Site]:
    for spec in SITES:
        site = db.scalar(select(Site).where(Site.code == spec["code"]))
        if site is None:
            site = site_service.create_site(
                db,
                {
                    "code": spec["code"],
                    "name": spec["name"],
                    "home_url": spec["home_url"],
                    "sitemap_url": spec["sitemap_url"],
                    "dept": spec["dept"],
                    "region": spec["region"],
                    "page_size": 12,
                    "max_depth": 3,
                    "note": spec["note"],
                },
            )
        else:
            site.home_url = spec["home_url"]
            site.sitemap_url = spec["sitemap_url"]
            site.note = spec["note"]
            db.flush()
    db.flush()
    return {site.code: site for site in db.scalars(select(Site)).all()}


def ensure_catalog(db, sites: dict[str, Site]) -> int:
    for spec in SITES:
        site = sites.get(spec["code"])
        if site is None:
            continue
        for row in fixture_site.catalog_rows(spec):
            exists = db.scalar(
                select(CatalogItem).where(CatalogItem.site_id == site.id, CatalogItem.entry_url == row["entry_url"])
            )
            if exists is None:
                db.add(
                    CatalogItem(
                        site_id=site.id,
                        column_code=row["column_code"],
                        column_name=row["column_name"],
                        entry_url=row["entry_url"],
                        canonical_url=row["canonical_url"],
                        page_no=row["page_no"],
                        item_no=row["item_no"],
                        depth=row["depth"],
                        discovered_from=row["discovered_from"],
                        title=row["title"],
                    )
                )
    db.flush()
    return db.scalar(select(func.count()).select_from(CatalogItem)) or 0


def ensure_sitemaps(db, sites: dict[str, Site]) -> int:
    for spec in SITES:
        site = sites.get(spec["code"])
        if site is None:
            continue
        for row in fixture_site.sitemap_rows(spec):
            exists = db.scalar(select(SitemapEntry).where(SitemapEntry.site_id == site.id, SitemapEntry.loc == row["loc"]))
            if exists is None:
                db.add(
                    SitemapEntry(
                        site_id=site.id,
                        loc=row["loc"],
                        canonical_url=row["canonical_url"],
                        lastmod=row["lastmod"],
                        changefreq=row["changefreq"],
                        priority=row["priority"],
                        source_file=row["source_file"],
                    )
                )
    db.flush()
    return db.scalar(select(func.count()).select_from(SitemapEntry)) or 0


def ensure_fixtures() -> None:
    for spec in SITES:
        info = fixture_site.ensure_site_fixture(spec)
        logger.info("[SEED_DEMO] fixture %s -> %s (files=%s)", spec["code"], info.get("root"), info.get("files"))


def ensure_run(db) -> int:
    crawl_run_service.create_and_execute(
        db,
        site_id=None,
        trigger="seed",
        operator_email=SEED_RUN_OPERATOR,
        seed_key=SEED_RUN_KEY,
    )
    return db.scalar(select(func.count()).select_from(CrawlRun)) or 0


def ensure_audit(db) -> None:
    seeds = [
        ("seed-audit-site", "admin@sitemapwatch.io", "admin", "site.create", "site", {"code": "zwgk-hezhou"}),
        ("seed-audit-crawl", "analyst@sitemapwatch.io", "analyst", "crawl.create", "crawl_run", {"run": SEED_RUN_KEY}),
        ("seed-audit-defect", "analyst@sitemapwatch.io", "analyst", "defect.review", "defect", {"status": "fixed"}),
    ]
    for seed_key, email, role, action, entity, detail in seeds:
        exists = db.scalar(select(AuditLog).where(AuditLog.seed_key == seed_key))
        if exists is None:
            db.add(
                AuditLog(
                    actor_email=email,
                    actor_role=role,
                    action=action,
                    entity=entity,
                    detail=detail,
                    layer="seed",
                    seed_key=seed_key,
                )
            )
    db.flush()


def seed_all() -> dict:
    with session_scope() as db:
        users = ensure_users(db)
        sites = ensure_sites(db)
        sites_total = db.scalar(select(func.count()).select_from(Site)) or 0
        logger.info("[SEED_DEMO] sites=%s", sites_total)
        catalog = ensure_catalog(db, sites)
        sitemap = ensure_sitemaps(db, sites)
        ensure_fixtures()
        runs = ensure_run(db)
        ensure_audit(db)
        defects = db.scalar(select(func.count()).select_from(Defect)) or 0
        pending = db.scalar(select(func.count()).select_from(Defect).where(Defect.status == "pending")) or 0
        summary = (
            f"SEED_SUMMARY brand=sitemapwatch users={users} sources={sites_total} "
            f"runs={runs} findings={defects} pending={pending}"
        )
        print(summary, flush=True)
        return {
            "users": users,
            "sites": sites_total,
            "catalog": catalog,
            "sitemap": sitemap,
            "runs": runs,
            "defects": defects,
            "pending": pending,
        }


if __name__ == "__main__":
    seed_all()
