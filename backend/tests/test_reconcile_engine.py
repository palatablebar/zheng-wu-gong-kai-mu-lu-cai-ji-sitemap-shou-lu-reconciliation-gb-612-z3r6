"""算法 B｜三向对账单测：分类、严重度、覆盖率手算、重定向/口径、重复 slug、确定性。"""
from __future__ import annotations

from src.services import reconcile_engine

HOME = "https://zwgk.hezhou.gov.cn"


def catalog(*paths: str) -> list[dict]:
    return [
        {
            "entry_url": f"{HOME}{path}",
            "canonical_url": f"{HOME}{path}",
            "column_name": "政策文件",
            "page_no": 1,
            "title": path,
        }
        for path in paths
    ]


def sitemap(*paths: str) -> list[dict]:
    return [
        {"loc": f"{HOME}{path}", "canonical_url": f"{HOME}{path}", "lastmod": "2026-10-01", "source_file": "sitemap.xml"}
        for path in paths
    ]


def probe(status: int = 200, chain: list[dict] | None = None, canonical_tag: str | None = None, final: str | None = None) -> dict:
    return {"status": status, "redirect_chain": chain or [], "canonical_tag": canonical_tag, "final_url": final, "loop": False}


def run(catalog_items, sitemap_rows, probes) -> dict:
    return reconcile_engine.reconcile(
        site_code="zwgk-hezhou",
        catalog_items=catalog_items,
        sitemap_locs=sitemap_rows,
        probes=probes,
    )


def test_only_in_catalog_is_p1():
    result = run(
        catalog("/a.html", "/b.html"),
        sitemap("/a.html"),
        {f"{HOME}/a.html": probe(), f"{HOME}/b.html": probe()},
    )
    categories = [item["category"] for item in result["defects"]]
    assert categories == ["only_in_catalog"]
    defect = result["defects"][0]
    assert defect["severity"] == "p1"
    assert defect["canonical_url"].endswith("/b.html")
    assert defect["evidence"]["in_sitemap"] is False


def test_dead_sitemap_entry_is_p0():
    result = run(
        catalog("/a.html"),
        sitemap("/a.html", "/gone.html"),
        {f"{HOME}/a.html": probe(), f"{HOME}/gone.html": probe(status=404)},
    )
    dead = [item for item in result["defects"] if item["category"] == "only_in_sitemap_dead"]
    assert len(dead) == 1
    assert dead[0]["severity"] == "p0"
    assert dead[0]["evidence"]["http_status"] == 404


def test_coverage_matches_hand_calculation():
    result = run(
        catalog("/a.html", "/b.html", "/c.html", "/d.html"),
        sitemap("/a.html", "/b.html", "/c.html", "/e.html"),
        {
            f"{HOME}/a.html": probe(),
            f"{HOME}/b.html": probe(),
            f"{HOME}/c.html": probe(),
            f"{HOME}/d.html": probe(),
            f"{HOME}/e.html": probe(status=404),
        },
    )
    stats = result["stats"]
    # |A| = 4，|A∩B| = 3，C ⊇ A → 覆盖率 3/4；e 死链 1 条
    assert stats["catalog_total"] == 4
    assert stats["sitemap_total"] == 4
    assert stats["hit"] == 3
    assert stats["coverage"] == 0.75
    assert stats["unreachable_rate"] == 0.0
    assert stats["dead"] == 1
    assert stats["p0"] == 1 and stats["p1"] == 1


def test_unreachable_catalog_entry_lowers_coverage():
    result = run(
        catalog("/a.html", "/b.html"),
        sitemap("/a.html", "/b.html"),
        {f"{HOME}/a.html": probe(), f"{HOME}/b.html": probe(status=410)},
    )
    assert result["stats"]["coverage"] == 0.5
    assert result["stats"]["unreachable_rate"] == 0.5
    assert result["stats"]["dead"] == 1


def test_redirect_and_canonical_mismatch():
    chain = [
        {
            "from": f"{HOME}/a.html",
            "to": f"{HOME}/b.html",
            "status": 301,
        }
    ]
    result = run(
        catalog("/a.html", "/c.html"),
        sitemap("/a.html", "/c.html"),
        {
            f"{HOME}/a.html": probe(chain=chain, final=f"{HOME}/b.html"),
            f"{HOME}/c.html": probe(canonical_tag=f"{HOME}/z.html"),
        },
    )
    by_category = {item["category"]: item for item in result["defects"]}
    assert set(by_category) == {"redirect_chain", "canonical_mismatch"}
    assert by_category["redirect_chain"]["severity"] == "p2"
    assert by_category["redirect_chain"]["evidence"]["hops"] == 1
    assert by_category["canonical_mismatch"]["severity"] == "p2"
    assert by_category["canonical_mismatch"]["evidence"]["page_canonical"].endswith("/z.html")


def test_duplicate_slug_from_two_entry_urls():
    items = [
        {"entry_url": f"{HOME}/col/", "canonical_url": f"{HOME}/col/", "column_name": "政策文件", "page_no": 1},
        {"entry_url": f"{HOME}/col/index.html", "canonical_url": f"{HOME}/col/", "column_name": "政策文件", "page_no": 1},
    ]
    result = run(items, sitemap("/col/"), {f"{HOME}/col/": probe()})
    duplicate = [item for item in result["defects"] if item["category"] == "duplicate_slug"]
    assert len(duplicate) == 1
    assert duplicate[0]["severity"] == "p1"
    assert len(duplicate[0]["evidence"]["entry_urls"]) == 2
    # 重复登记不应额外报「漏收」
    assert result["stats"]["catalog_total"] == 1


def test_deterministic_and_sorted():
    catalog_items = catalog("/a.html", "/b.html", "/c.html")
    sitemap_rows = sitemap("/a.html", "/dead.html")
    probes = {
        f"{HOME}/a.html": probe(),
        f"{HOME}/b.html": probe(),
        f"{HOME}/c.html": probe(),
        f"{HOME}/dead.html": probe(status=404),
    }
    first = run(catalog_items, sitemap_rows, probes)
    second = run(catalog_items, sitemap_rows, probes)
    assert first == second
    severities = [item["severity"] for item in first["defects"]]
    assert severities == sorted(severities)


def test_gap_entry_is_not_counted_as_p0_dead_link():
    # 失败子清单沿用的地址即使探测 404，也按缺口（P2）处理，绝不报 P0 死链
    gap_sitemap = [
        {
            "loc": f"{HOME}/gone.html",
            "canonical_url": f"{HOME}/gone.html",
            "lastmod": "2026-09-01",
            "source_file": "sitemap-failed.xml",
            "is_gap": True,
        }
    ]
    result = run(
        catalog("/a.html"),
        gap_sitemap,
        {f"{HOME}/a.html": probe(), f"{HOME}/gone.html": probe(status=404)},
    )
    gap = [item for item in result["defects"] if item["category"] == "only_in_sitemap_dead"]
    assert len(gap) == 1
    assert gap[0]["severity"] == "p2"
    assert gap[0]["evidence"]["is_gap"] is True
    assert gap[0]["evidence"]["source_file"] == "sitemap-failed.xml"
    # 缺口不计入 dead，单独计入 gap_entries
    assert result["stats"]["dead"] == 0
    assert result["stats"]["gap_entries"] == 1
    assert result["stats"]["p0"] == 0
    assert result["stats"]["p2"] == 1


def test_normal_dead_link_still_p0_alongside_gap():
    mixed_sitemap = [
        {
            "loc": f"{HOME}/gap.html",
            "canonical_url": f"{HOME}/gap.html",
            "lastmod": "2026-09-01",
            "source_file": "sitemap-failed.xml",
            "is_gap": True,
        },
        {
            "loc": f"{HOME}/dead.html",
            "canonical_url": f"{HOME}/dead.html",
            "lastmod": "2026-09-01",
            "source_file": "sitemap-ok.xml",
            "is_gap": False,
        },
    ]
    result = run(
        catalog("/a.html"),
        mixed_sitemap,
        {
            f"{HOME}/a.html": probe(),
            f"{HOME}/gap.html": probe(status=404),
            f"{HOME}/dead.html": probe(status=404),
        },
    )
    dead = [item for item in result["defects"] if item["category"] == "only_in_sitemap_dead"]
    by_url = {item["canonical_url"]: item for item in dead}
    assert by_url[f"{HOME}/dead.html"]["severity"] == "p0"
    assert by_url[f"{HOME}/gap.html"]["severity"] == "p2"
    assert result["stats"]["dead"] == 1
    assert result["stats"]["gap_entries"] == 1
    assert result["stats"]["p0"] == 1
