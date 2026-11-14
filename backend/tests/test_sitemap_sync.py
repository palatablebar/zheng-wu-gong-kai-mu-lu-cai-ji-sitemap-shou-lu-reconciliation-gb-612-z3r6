"""端到端集成：fixture 子清单 → 版本化同步 → 裁决 → 巡检快照 → 对账/增量重算。

用 SQLite 内存库跑完整服务层（不依赖 MySQL/网络），验证：
1. 多子清单按 lastmod 裁决，迟到旧清单不覆盖生效地址；
2. 失败子清单沿用上一版并标缺口，不触发误删，对账不报 P0 死链；
3. 单文件变化后增量巡检只重算受影响站点；
4. 对账、覆盖率、导出读同一轮 CrawlRunSitemap 快照。
"""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from src.constants.demo_data import SITES
from src.models import Base
from src.models.crawl_run_sitemap import CrawlRunSitemap
from src.models.site import Site
from src.models.sitemap_entry import SitemapEntry
from src.models.sitemap_source import SitemapSource, SitemapVersion
from src.services import crawl_run_service, fixture_site, sitemap_sync


@pytest.fixture()
def db_session(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)()
    # 把 fixture 根目录指到临时目录
    fixture_site.FIXTURE_BASE = tmp_path / "sample_site"
    yield session
    session.close()
    engine.dispose()


def _make_site(session, spec) -> Site:
    site = Site(
        code=spec["code"],
        name=spec["name"],
        home_url=spec["home_url"],
        sitemap_url=spec["sitemap_url"],
        dept=spec["dept"],
        region=spec["region"],
    )
    session.add(site)
    session.flush()
    fixture_site.build_site(spec, fixture_site.fixture_root(spec["code"]))
    return site


def test_full_sync_creates_sources_versions_round_and_entries(db_session):
    spec = SITES[0]
    site = _make_site(db_session, spec)
    round_row = sitemap_sync.sync_fixture_site(db_session, site, spec, triggered_by="test")

    expected = len(fixture_site.sitemap_rows(spec))
    assert round_row.status == "success"
    assert round_row.entry_total == expected
    sources = db_session.scalars(select(SitemapSource).where(SitemapSource.site_id == site.id)).all()
    assert len(sources) == 7  # 6 个栏目子清单 + 1 个 archived
    assert all(source.status == "ok" for source in sources)
    versions = db_session.scalars(select(SitemapVersion).where(SitemapVersion.site_id == site.id)).all()
    assert len(versions) == 7
    assert all(version.status == "ok" for version in versions)
    entries = db_session.scalars(select(SitemapEntry).where(SitemapEntry.site_id == site.id)).all()
    assert len(entries) == expected
    # 来源与 lastmod 被保留
    assert all(entry.source_file.startswith("sitemap-") for entry in entries)
    assert all(entry.is_gap is False for entry in entries)
    # 每条地址都有 lastmod
    assert all(entry.lastmod for entry in entries)


def test_failed_source_reuses_previous_version_and_marks_gap(db_session):
    spec = SITES[0]
    site = _make_site(db_session, spec)
    sitemap_sync.sync_fixture_site(db_session, site, spec, triggered_by="test")
    before = {row.canonical_url: row for row in db_session.scalars(
        select(SitemapEntry).where(SitemapEntry.site_id == site.id)
    ).all()}

    # 第二轮：其中一个栏目子清单超时
    failing = "sitemap-zcwj.xml"
    second = sitemap_sync.sync_fixture_site(
        db_session, site, spec, fail_sources={failing}, triggered_by="test"
    )
    assert second.status == "partial"
    assert second.source_failed == 1
    assert second.gap_count > 0

    source = db_session.scalar(
        select(SitemapSource).where(
            SitemapSource.site_id == site.id, SitemapSource.source_file == failing
        )
    )
    assert source.status == "stale_gap"
    # 失败轮不刷新成功指纹
    failed_version = db_session.scalar(
        select(SitemapVersion)
        .where(SitemapVersion.source_id == source.id, SitemapVersion.status == "failed")
        .order_by(SitemapVersion.id.desc())
    )
    assert failed_version is not None
    assert failed_version.content_hash is None
    assert source.last_success_hash is not None

    after = {row.canonical_url: row for row in db_session.scalars(
        select(SitemapEntry).where(SitemapEntry.site_id == site.id)
    ).all()}
    # 关键：失败源的地址一条都不能少（不能被当成下线）
    failed_urls = {url for url, row in before.items() if row.source_file == failing}
    assert failed_urls.issubset(set(after))
    gap_rows = [row for row in after.values() if row.is_gap]
    assert {row.canonical_url for row in gap_rows} == failed_urls

    # 恢复后第三轮：缺口清除
    third = sitemap_sync.sync_fixture_site(db_session, site, spec, triggered_by="test")
    assert third.status == "success"
    assert third.gap_count == 0
    still_gap = db_session.scalar(
        select(SitemapEntry).where(SitemapEntry.site_id == site.id, SitemapEntry.is_gap.is_(True))
    )
    assert still_gap is None


def test_late_manifest_with_older_lastmod_keeps_effective_version(db_session):
    spec = SITES[0]
    site = _make_site(db_session, spec)
    sitemap_sync.sync_fixture_site(db_session, site, spec, triggered_by="test")
    target = db_session.scalars(select(SitemapEntry).where(SitemapEntry.site_id == site.id)).first()
    canonical = target.canonical_url
    original_lastmod = target.lastmod
    original_source = target.source_file

    # 迟到清单带来同一地址的旧 lastmod 记录
    stale = [
        {
            "loc": target.loc,
            "canonical_url": canonical,
            "lastmod": "2020-01-01",
            "source_file": "sitemap-late.xml",
            "changefreq": "monthly",
            "priority": 0.3,
        }
    ]
    round_row = sitemap_sync.sync_from_payload(
        db_session,
        site,
        [
            {"source_file": "sitemap-late.xml", "ok": True, "entries": stale},
        ],
        triggered_by="test",
    )
    db_session.expire_all()
    refreshed = db_session.scalar(
        select(SitemapEntry).where(
            SitemapEntry.site_id == site.id, SitemapEntry.canonical_url == canonical
        )
    )
    assert refreshed.lastmod == original_lastmod
    assert refreshed.source_file == original_source
    assert round_row.stats["kept"] >= 1


def test_crawl_run_freezes_snapshot_and_reconcile_uses_it(db_session):
    spec = SITES[0]
    site = _make_site(db_session, spec)
    sitemap_sync.sync_fixture_site(db_session, site, spec, triggered_by="test")

    # 补目录条目（算法 B 的 A 集合）
    from src.models.catalog_item import CatalogItem

    for row in fixture_site.catalog_rows(spec):
        db_session.add(
            CatalogItem(
                site_id=site.id,
                column_code=row["column_code"],
                column_name=row["column_name"],
                entry_url=row["entry_url"],
                canonical_url=row["canonical_url"],
                page_no=row["page_no"],
                item_no=row["item_no"],
                depth=2,
                discovered_from="rel_next",
                title=row["title"],
            )
        )
    db_session.flush()

    run = crawl_run_service.create_and_execute(
        db_session, site_id=site.id, trigger="manual", operator_email="t@example.io"
    )
    assert run.status == "success"
    # 快照条数 = 生效地址条数
    snap_count = db_session.scalar(
        select(func.count()).select_from(CrawlRunSitemap).where(CrawlRunSitemap.run_id == run.id)
    )
    live_count = db_session.scalar(
        select(func.count()).select_from(SitemapEntry).where(SitemapEntry.site_id == site.id)
    )
    assert snap_count == live_count
    assert str(site.id) in run.sitemap_round_ids

    # 巡检后再同步一轮新清单（模拟清单变化），历史巡检快照不应被改写
    round_before = run.sitemap_round_ids[str(site.id)]
    sitemap_sync.sync_fixture_site(db_session, site, spec, triggered_by="test")
    snap_after = db_session.scalar(
        select(func.count()).select_from(CrawlRunSitemap).where(CrawlRunSitemap.run_id == run.id)
    )
    assert snap_after == snap_count
    assert run.sitemap_round_ids[str(site.id)] == round_before


def test_incremental_run_recomputes_only_affected_sites(db_session):
    specs = SITES[:2]
    sites = []
    for spec in specs:
        site = _make_site(db_session, spec)
        sitemap_sync.sync_fixture_site(db_session, site, spec, triggered_by="test")
        sites.append(site)

    # 全量基线巡检
    baseline = crawl_run_service.create_and_execute(
        db_session, site_id=None, trigger="manual", operator_email="t@example.io"
    )
    assert baseline.status == "success"
    assert set(baseline.metrics["sites_crawled"]) == {specs[0]["code"], specs[1]["code"]}

    # 没有任何清单变化 → 增量巡检没有受影响站点，全部沿用上一轮
    noop = crawl_run_service.create_and_execute(
        db_session,
        site_id=None,
        trigger="manual",
        operator_email="t@example.io",
        incremental=True,
    )
    assert noop.status == "partial"
    assert noop.metrics["sites_crawled"] == []
    assert set(noop.metrics["skipped_sites"]) == {specs[0]["code"], specs[1]["code"]}
    carried = {item["code"]: item for item in noop.metrics["sites"]}
    assert all(item["recomputed"] is False for item in carried.values())
    # 沿用指标与基线一致
    base_metrics = {item["code"]: item for item in baseline.metrics["sites"]}
    for code, item in carried.items():
        assert item["coverage"] == base_metrics[code]["coverage"]
        assert item["defects"] == base_metrics[code]["defects"]

    # 只让第一个站点的一个子清单失败 → 仅该站点受影响需要重算
    sitemap_sync.sync_fixture_site(
        db_session, sites[0], specs[0], fail_sources={"sitemap-zcwj.xml"}, triggered_by="test"
    )
    targeted = crawl_run_service.create_and_execute(
        db_session,
        site_id=None,
        trigger="manual",
        operator_email="t@example.io",
        incremental=True,
    )
    assert targeted.metrics["sites_crawled"] == [specs[0]["code"]]
    assert targeted.metrics["skipped_sites"] == [specs[1]["code"]]
    recomputed = {item["code"]: item for item in targeted.metrics["sites"] if item["recomputed"]}
    assert list(recomputed) == [specs[0]["code"]]


def test_gap_entries_do_not_produce_p0_dead_links(db_session):
    from src.models.catalog_item import CatalogItem

    spec = SITES[0]
    site = _make_site(db_session, spec)
    sitemap_sync.sync_fixture_site(db_session, site, spec, triggered_by="test")
    for row in fixture_site.catalog_rows(spec):
        db_session.add(
            CatalogItem(
                site_id=site.id,
                column_code=row["column_code"],
                column_name=row["column_name"],
                entry_url=row["entry_url"],
                canonical_url=row["canonical_url"],
                page_no=row["page_no"],
                item_no=row["item_no"],
                depth=2,
                discovered_from="rel_next",
                title=row["title"],
            )
        )
    db_session.flush()

    # 制造一个失败源：它包含的 archived 死链地址必须沿用且不算新 P0
    failing = "sitemap-archived.xml"
    sitemap_sync.sync_fixture_site(
        db_session, site, spec, fail_sources={failing}, triggered_by="test"
    )
    run = crawl_run_service.create_and_execute(
        db_session, site_id=site.id, trigger="manual", operator_email="t@example.io"
    )
    site_metrics = run.metrics["sites"][0]
    assert site_metrics["gap_entries"] > 0
    # 缺口里的 archived 死链不应计入 dead（P0）
    gap_snapshot = db_session.scalars(
        select(CrawlRunSitemap).where(
            CrawlRunSitemap.run_id == run.id, CrawlRunSitemap.is_gap.is_(True)
        )
    ).all()
    assert any(row.source_file == failing for row in gap_snapshot)
