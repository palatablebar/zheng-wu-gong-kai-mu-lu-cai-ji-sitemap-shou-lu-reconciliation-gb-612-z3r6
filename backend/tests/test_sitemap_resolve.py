"""子清单裁决纯函数单测：lastmod 裁决、迟到旧清单、失败沿用缺口、指纹差分。"""
from __future__ import annotations

from src.services.sitemap_resolve import (
    ACTION_ADDED,
    ACTION_KEPT,
    ACTION_REMOVED,
    ACTION_REUSED,
    ACTION_UPDATED,
    ROUND_PARTIAL,
    ROUND_SUCCESS,
    SourceInput,
    affected_canonicals,
    diff_source_hashes,
    parse_lastmod,
    resolve_round,
)

HOME = "https://zwgk.hezhou.gov.cn"


def entry(path: str, lastmod: str, source: str) -> dict:
    return {
        "loc": f"{HOME}{path}",
        "canonical_url": f"{HOME}{path}",
        "lastmod": lastmod,
        "changefreq": "weekly",
        "priority": 0.8,
        "source_file": source,
    }


def source(name: str, entries: list[dict], ok: bool = True, error: str | None = None) -> SourceInput:
    return SourceInput(source_file=name, ok=ok, entries=entries, error=error, content_hash=f"h-{name}-{len(entries)}")


def test_lastmod_parser_supports_date_and_datetime():
    assert parse_lastmod("2026-10-08") == parse_lastmod("2026-10-08T12:00:00+08:00")
    assert parse_lastmod(None) is None
    assert parse_lastmod("not-a-date") is None


def test_first_round_adds_everything():
    result = resolve_round(
        [source("sitemap-a.xml", [entry("/a.html", "2026-10-01", "sitemap-a.xml")])]
    )
    assert result["status"] == ROUND_SUCCESS
    assert result["stats"]["total"] == 1
    assert result["stats"]["added"] == 1
    assert result["actions"][f"{HOME}/a.html"] == ACTION_ADDED


def test_late_old_manifest_cannot_overwrite_newer_effective_entry():
    # 已生效版本 lastmod=2026-10-05，迟到清单只带来 2026-09-01 的旧记录
    previous = {
        f"{HOME}/a.html": entry("/a.html", "2026-10-05", "sitemap-a.xml"),
    }
    result = resolve_round(
        [source("sitemap-b.xml", [entry("/a.html", "2026-09-01", "sitemap-b.xml")])],
        previous=previous,
    )
    winner = result["by_canonical"][f"{HOME}/a.html"]
    assert winner["lastmod"] == "2026-10-05"
    assert winner["source_file"] == "sitemap-a.xml"
    assert result["actions"][f"{HOME}/a.html"] == ACTION_KEPT


def test_newer_lastmod_from_late_manifest_wins():
    previous = {f"{HOME}/a.html": entry("/a.html", "2026-10-05", "sitemap-a.xml")}
    result = resolve_round(
        [source("sitemap-b.xml", [entry("/a.html", "2026-11-01", "sitemap-b.xml")])],
        previous=previous,
    )
    winner = result["by_canonical"][f"{HOME}/a.html"]
    assert winner["lastmod"] == "2026-11-01"
    assert winner["source_file"] == "sitemap-b.xml"
    assert result["actions"][f"{HOME}/a.html"] == ACTION_UPDATED


def test_same_lastmod_keeps_first_source_deterministically():
    result = resolve_round(
        [
            source("sitemap-a.xml", [entry("/a.html", "2026-10-01", "sitemap-a.xml")]),
            source("sitemap-b.xml", [entry("/a.html", "2026-10-01", "sitemap-b.xml")]),
        ]
    )
    winner = result["by_canonical"][f"{HOME}/a.html"]
    assert winner["source_file"] == "sitemap-a.xml"


def test_failed_source_reuses_previous_and_marks_gap():
    previous = {
        f"{HOME}/a.html": entry("/a.html", "2026-10-01", "sitemap-a.xml"),
        f"{HOME}/b.html": entry("/b.html", "2026-10-02", "sitemap-b.xml"),
    }
    result = resolve_round(
        [
            source("sitemap-a.xml", [], ok=False, error="timeout"),
            source("sitemap-b.xml", [entry("/b.html", "2026-10-02", "sitemap-b.xml")]),
        ],
        previous=previous,
    )
    assert result["status"] == ROUND_PARTIAL
    assert result["failed_sources"] == ["sitemap-a.xml"]
    reused = result["by_canonical"][f"{HOME}/a.html"]
    assert reused["is_gap"] is True
    assert reused["action"] == ACTION_REUSED
    assert f"{HOME}/a.html" in result["gaps"]
    # b 源正常，地址保持生效且不是缺口
    assert result["by_canonical"][f"{HOME}/b.html"]["is_gap"] is False


def test_failed_source_does_not_trigger_removal():
    # 失败源的旧地址绝不能因为"本轮没出现"被判下线
    previous = {f"{HOME}/a.html": entry("/a.html", "2026-10-01", "sitemap-a.xml")}
    result = resolve_round(
        [source("sitemap-a.xml", [], ok=False, error="504")],
        previous=previous,
    )
    assert ACTION_REMOVED not in result["actions"].values()
    assert result["stats"]["total"] == 1
    assert result["stats"]["reused_gap"] == 1


def test_successful_source_removes_entries_it_no_longer_lists():
    previous = {
        f"{HOME}/a.html": entry("/a.html", "2026-10-01", "sitemap-a.xml"),
        f"{HOME}/b.html": entry("/b.html", "2026-10-02", "sitemap-a.xml"),
    }
    result = resolve_round(
        [source("sitemap-a.xml", [entry("/a.html", "2026-10-01", "sitemap-a.xml")])],
        previous=previous,
    )
    assert result["actions"][f"{HOME}/b.html"] == ACTION_REMOVED
    assert f"{HOME}/b.html" not in result["by_canonical"]


def test_recovery_round_clears_gap():
    previous = {f"{HOME}/a.html": entry("/a.html", "2026-10-01", "sitemap-a.xml")}
    failed = resolve_round(
        [source("sitemap-a.xml", [], ok=False, error="timeout")],
        previous=previous,
    )
    assert failed["by_canonical"][f"{HOME}/a.html"]["is_gap"] is True
    recovered = resolve_round(
        [source("sitemap-a.xml", [entry("/a.html", "2026-10-01", "sitemap-a.xml")])],
        previous={item["canonical_url"]: item for item in failed["entries"]},
    )
    assert recovered["by_canonical"][f"{HOME}/a.html"]["is_gap"] is False
    assert recovered["gaps"] == []


def test_diff_source_hashes_detects_single_file_change():
    previous = {"a.xml": "h1", "b.xml": "h2"}
    assert diff_source_hashes({"a.xml": "h1", "b.xml": "h9"}, previous) == ["b.xml"]
    assert diff_source_hashes({"a.xml": "h1", "b.xml": "h2"}, previous) == []
    assert diff_source_hashes({"a.xml": "h1", "b.xml": "h2", "c.xml": "h3"}, previous) == ["c.xml"]


def test_affected_canonicals_excludes_kept_and_reused():
    actions = {
        "/new": ACTION_ADDED,
        "/changed": ACTION_UPDATED,
        "/same": ACTION_KEPT,
        "/gap": ACTION_REUSED,
        "/gone": ACTION_REMOVED,
    }
    touched = affected_canonicals(actions)
    assert touched == {"/new", "/changed", "/gone"}


def test_record_with_lastmod_replaces_version_without_lastmod():
    previous = {f"{HOME}/a.html": entry("/a.html", None, "sitemap-a.xml")}
    result = resolve_round(
        [source("sitemap-b.xml", [entry("/a.html", "2026-11-01", "sitemap-b.xml")])],
        previous=previous,
    )
    winner = result["by_canonical"][f"{HOME}/a.html"]
    assert winner["lastmod"] == "2026-11-01"
    assert winner["source_file"] == "sitemap-b.xml"
    assert result["actions"][f"{HOME}/a.html"] == ACTION_UPDATED


def test_record_without_lastmod_never_overwrites_dated_version():
    previous = {f"{HOME}/a.html": entry("/a.html", "2026-10-01", "sitemap-a.xml")}
    result = resolve_round(
        [source("sitemap-b.xml", [entry("/a.html", None, "sitemap-b.xml")])],
        previous=previous,
    )
    winner = result["by_canonical"][f"{HOME}/a.html"]
    assert winner["lastmod"] == "2026-10-01"
    assert result["actions"][f"{HOME}/a.html"] == ACTION_KEPT
