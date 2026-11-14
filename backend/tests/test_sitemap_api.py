"""HTTP 层测试：sitemap 同步/查询路由、RBAC、快照口径（TestClient + SQLite）。

不触发 FastAPI lifespan（避免连默认 Postgres/自动 seed），而是直接替换
``src.config.database`` 的 engine 与 SessionLocal，让路由依赖与中间件都用 SQLite。
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.config import database
from src.config.app import create_app
from src.constants.demo_data import SITES
from src.models import Base
from src.models.site import Site
from src.services import fixture_site, sitemap_sync
from src.utils.security import create_access_token


@pytest.fixture()
def client(tmp_path):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    testing_session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    # 中间件（审计）与路由 get_db 都从 database 模块取 engine/SessionLocal
    original_engine = database.engine
    original_session = database.SessionLocal
    database.engine = engine
    database.SessionLocal = testing_session
    fixture_site.FIXTURE_BASE = tmp_path / "sample_site"

    app = create_app()

    def override_get_db():
        db = testing_session()
        try:
            yield db
            db.commit()
        finally:
            db.close()

    app.dependency_overrides[database.get_db] = override_get_db
    # 不使用 with 上下文，避免 lifespan 去连默认数据库
    test_client = TestClient(app)
    try:
        yield test_client, testing_session, engine
    finally:
        test_client.close()
        app.dependency_overrides.clear()
        database.engine = original_engine
        database.SessionLocal = original_session
        engine.dispose()


def _auth(role_email: str, role: str) -> dict:
    token, _ = create_access_token(role_email, role)
    return {"Authorization": f"Bearer {token}"}


def _seed_site(session_factory, spec) -> Site:
    db = session_factory()
    site = Site(
        code=spec["code"],
        name=spec["name"],
        home_url=spec["home_url"],
        sitemap_url=spec["sitemap_url"],
        dept=spec["dept"],
        region=spec["region"],
    )
    db.add(site)
    db.flush()
    fixture_site.build_site(spec, fixture_site.fixture_root(spec["code"]))
    sitemap_sync.sync_fixture_site(db, site, spec, triggered_by="test")
    db.commit()
    site_id = site.id
    db.close()
    return site_id


def test_rounds_and_sources_endpoints(client):
    test_client, session_factory, _ = client
    site_id = _seed_site(session_factory, SITES[0])
    resp = test_client.get("/api/sitemaps/rounds", params={"site_id": site_id}, headers=_auth("v@x.io", "viewer"))
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["status"] == "success"
    assert body["items"][0]["entry_total"] == len(fixture_site.sitemap_rows(SITES[0]))

    sources = test_client.get("/api/sitemaps/sources", params={"site_id": site_id}, headers=_auth("v@x.io", "viewer"))
    assert sources.status_code == 200
    assert sources.json()["total"] == 7

    versions = test_client.get(
        f"/api/sitemaps/sources/{sources.json()['items'][0]['id']}/versions",
        headers=_auth("v@x.io", "viewer"),
    )
    assert versions.status_code == 200
    assert versions.json()["items"][0]["status"] == "ok"


def test_viewer_cannot_sync_but_analyst_can(client):
    test_client, session_factory, _ = client
    site_id = _seed_site(session_factory, SITES[0])
    denied = test_client.post(
        "/api/sitemaps/sync-fixture",
        json={"site_id": site_id, "fail_sources": []},
        headers=_auth("viewer@x.io", "viewer"),
    )
    assert denied.status_code == 403

    ok = test_client.post(
        "/api/sitemaps/sync-fixture",
        json={"site_id": site_id, "fail_sources": ["sitemap-zcwj.xml"]},
        headers=_auth("analyst@x.io", "analyst"),
    )
    assert ok.status_code == 201
    round_row = ok.json()["items"][0]
    assert round_row["status"] == "partial"
    assert round_row["gap_count"] > 0

    gaps = test_client.get(
        "/api/sitemaps",
        params={"site_id": site_id, "is_gap": "true"},
        headers=_auth("v@x.io", "viewer"),
    )
    assert gaps.status_code == 200
    assert gaps.json()["total"] == round_row["gap_count"]
    assert all(item["is_gap"] for item in gaps.json()["items"])


def test_sync_payload_endpoint_resolves_lastmod(client):
    test_client, session_factory, _ = client
    site_id = _seed_site(session_factory, SITES[0])
    db = session_factory()
    site = db.get(Site, site_id)
    home = site.home_url
    db.close()
    payload = {
        "site_id": site_id,
        "sources": [
            {
                "source_file": "manual-extra.xml",
                "ok": True,
                "entries": [
                    {
                        "loc": f"{home}/xxgk/zcwj/extra-900.html",
                        "lastmod": "2026-11-01",
                    }
                ],
            }
        ],
    }
    resp = test_client.post("/api/sitemaps/sync", json=payload, headers=_auth("admin@x.io", "admin"))
    assert resp.status_code == 201
    assert resp.json()["stats"]["added"] >= 1


def test_unauthenticated_request_is_401(client):
    test_client, _session, _ = client
    resp = test_client.get("/api/sitemaps/rounds")
    assert resp.status_code == 401


def test_crawl_run_endpoint_freezes_snapshot(client):
    test_client, session_factory, _ = client
    site_id = _seed_site(session_factory, SITES[0])
    # 补目录条目
    from src.models.catalog_item import CatalogItem

    db = session_factory()
    spec = SITES[0]
    for row in fixture_site.catalog_rows(spec):
        db.add(
            CatalogItem(
                site_id=site_id,
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
    db.commit()
    db.close()

    resp = test_client.post(
        "/api/crawl-runs",
        json={"site_id": site_id, "trigger": "manual", "incremental": False},
        headers=_auth("analyst@x.io", "analyst"),
    )
    assert resp.status_code == 201
    run = resp.json()
    assert run["status"] == "success"
    assert str(site_id) in run["sitemap_round_ids"]
    assert run["metrics"]["sites"][0]["gap_entries"] == 0


def test_coverage_export_uses_frozen_snapshot(client):
    test_client, session_factory, _ = client
    site_id = _seed_site(session_factory, SITES[0])
    from src.models.catalog_item import CatalogItem

    db = session_factory()
    spec = SITES[0]
    for row in fixture_site.catalog_rows(spec):
        db.add(
            CatalogItem(
                site_id=site_id,
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
    db.commit()
    run_resp = test_client.post(
        "/api/crawl-runs",
        json={"site_id": site_id, "trigger": "manual"},
        headers=_auth("analyst@x.io", "analyst"),
    )
    run_id = run_resp.json()["id"]

    # 巡检后再同步一轮（内容不变，只是产生新一轮），导出仍锚定旧巡检快照
    test_client.post(
        "/api/sitemaps/sync-fixture",
        json={"site_id": site_id, "fail_sources": []},
        headers=_auth("admin@x.io", "admin"),
    )
    export = test_client.get(
        "/api/exports/coverage.csv",
        params={"run_id": run_id},
        headers=_auth("admin@x.io", "admin"),
    )
    assert export.status_code == 200
    text = export.content.decode("utf-8-sig")
    assert "sitemap loc B（快照）" in text
    assert "缺口沿用数" in text
    # ALL 行的 B 列等于该轮快照数
    lines = [line for line in text.strip().splitlines() if line]
    all_row = lines[-1]
    assert f",{len(fixture_site.sitemap_rows(spec))}," in all_row

    # viewer 不能导出 → 403
    denied = test_client.get(
        "/api/exports/coverage.csv",
        params={"run_id": run_id},
        headers=_auth("viewer@x.io", "viewer"),
    )
    assert denied.status_code == 403
