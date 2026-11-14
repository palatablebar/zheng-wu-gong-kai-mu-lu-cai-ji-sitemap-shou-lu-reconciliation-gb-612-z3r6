"""sitemap 子清单同步服务：拉取留痕 → 版本化 → 按 lastmod 裁决 → 生效地址落库。

关键口径（与 ``sitemap_resolve`` 纯函数一致，本模块负责数据库事务）：
1. 每份子清单每次到达都写一条不可变 ``SitemapVersion``；失败只记错误、不更新
   ``last_success_hash``，裁决时沿用上一版并把来源标成 ``stale_gap``；
2. 同一 canonical 按 lastmod 裁决，迟到的旧清单不能覆盖已生效地址；
3. 每轮产生一条 ``SitemapRound``，记录内容指纹与裁决统计；
4. ``SitemapEntry`` 是"当前生效版本"，来源与最后修改时间随记录保留；
5. 提供受影响站点判断：只有子清单内容指纹变化的站点才需要重算对账。
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.models.crawl_run import CrawlRun
from src.models.site import Site
from src.models.sitemap_entry import SitemapEntry
from src.models.sitemap_round import SitemapRound
from src.models.sitemap_source import SitemapSource, SitemapVersion
from src.services import fixture_site
from src.services.sitemap_parser import SitemapParseError, parse_sitemap, source_filename
from src.services.sitemap_resolve import (
    ACTION_REMOVED,
    SOURCE_FAILED,
    SOURCE_STALE_GAP,
    SOURCE_OK,
    SourceInput,
    diff_source_hashes,
    resolve_round,
)
from src.services.url_normalize import normalize_url
from src.utils.timeutil import local_now, utcnow


def _fingerprint(entries: list[dict]) -> str:
    """子清单内容指纹：归一后按 canonical 排序，保证同内容同指纹。"""
    slim = sorted(
        (
            {
                "canonical_url": normalize_url(row.get("canonical_url") or row.get("loc")),
                "lastmod": row.get("lastmod"),
                "changefreq": row.get("changefreq"),
                "priority": float(row.get("priority") or 0.8),
            }
            for row in entries
        ),
        key=lambda item: item["canonical_url"],
    )
    blob = json.dumps(slim, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def next_round_no(db: Session, site_id: int) -> str:
    prefix = f"SR{local_now():%Y%m%d}-S{site_id}"
    total = (
        db.scalar(select(func.count()).select_from(SitemapRound).where(SitemapRound.site_id == site_id)) or 0
    )
    return f"{prefix}-{total + 1:03d}"


def _previous_entries(db: Session, site_id: int) -> dict[str, dict]:
    rows = db.scalars(select(SitemapEntry).where(SitemapEntry.site_id == site_id)).all()
    return {
        row.canonical_url: {
            "loc": row.loc,
            "canonical_url": row.canonical_url,
            "lastmod": row.lastmod,
            "changefreq": row.changefreq,
            "priority": row.priority,
            "source_file": row.source_file,
            "is_gap": row.is_gap,
        }
        for row in rows
    }


def _get_or_create_source(db: Session, site_id: int, source_file: str, source_url: str | None) -> SitemapSource:
    source = db.scalar(
        select(SitemapSource).where(
            SitemapSource.site_id == site_id, SitemapSource.source_file == source_file
        )
    )
    if source is None:
        source = SitemapSource(site_id=site_id, source_file=source_file, source_url=source_url)
        db.add(source)
        db.flush()
    elif source_url and source.source_url != source_url:
        source.source_url = source_url
    return source


def read_fixture_source(spec: dict, source_file: str) -> list[dict]:
    """从离线 fixture 站读一份子清单（网络拉取的本地替身）。"""
    root = fixture_site.fixture_root(spec["code"])
    path = Path(root) / source_file
    xml_text = path.read_text(encoding="utf-8")
    parsed = parse_sitemap(xml_text)
    if parsed["kind"] != "urlset":
        raise SitemapParseError(f"{source_file} 不是 urlset 子清单")
    home = spec["home_url"].rstrip("/")
    rows = []
    for item in parsed["urls"]:
        loc = item["loc"]
        rows.append(
            {
                "loc": loc,
                "canonical_url": normalize_url(loc, base=home),
                "lastmod": item.get("lastmod"),
                "changefreq": item.get("changefreq") or "weekly",
                "priority": item.get("priority") or 0.8,
                "source_file": source_file,
            }
        )
    return rows


def discover_fixture_sources(spec: dict) -> list[dict]:
    """读 sitemap index，返回登记用的子清单描述（文件名 + URL）。"""
    root = fixture_site.fixture_root(spec["code"])
    index_path = Path(root) / "sitemap.xml"
    parsed = parse_sitemap(index_path.read_text(encoding="utf-8"))
    home = spec["home_url"].rstrip("/")
    if parsed["kind"] == "index":
        return [
            {
                "source_file": source_filename(child["loc"]),
                "source_url": child["loc"],
                "lastmod": child.get("lastmod"),
            }
            for child in parsed["children"]
        ]
    # 兼容单文件 sitemap
    return [{"source_file": "sitemap.xml", "source_url": f"{home}/sitemap.xml", "lastmod": None}]


def apply_round(db: Session, site: Site, inputs: list[SourceInput], *, triggered_by: str) -> SitemapRound:
    """对一个站点执行一轮同步：版本留痕 + lastmod 裁决 + 生效地址 upsert。"""
    site_id = site.id
    previous = _previous_entries(db, site_id)
    result = resolve_round(inputs, previous)

    round_row = SitemapRound(
        site_id=site_id,
        round_no=next_round_no(db, site_id),
        status=result["status"],
        source_total=len(inputs),
        source_failed=len(result["failed_sources"]),
        entry_total=result["stats"]["total"],
        gap_count=result["stats"]["reused_gap"],
        source_hashes={item.source_file: item.content_hash for item in inputs if item.content_hash},
        stats=result["stats"],
        triggered_by=triggered_by,
    )
    db.add(round_row)
    db.flush()

    now = utcnow()
    for item in inputs:
        source = _get_or_create_source(
            db,
            site_id,
            item.source_file,
            source_url=None,
        )
        source.last_attempt_at = now
        if item.ok:
            source.status = SOURCE_OK
            source.last_error = None
            source.last_success_hash = item.content_hash
            source.last_success_at = now
        else:
            # 失败不刷新成功指纹；若还有上一版数据可沿用，标缺口而不是失联
            source.status = SOURCE_STALE_GAP if source.last_success_hash else SOURCE_FAILED
            source.last_error = (item.error or "拉取失败")[:500]
        db.add(
            SitemapVersion(
                source_id=source.id,
                site_id=site_id,
                round_id=round_row.id,
                status="ok" if item.ok else "failed",
                content_hash=item.content_hash,
                entry_count=len(item.entries),
                payload={"entries": item.entries} if item.ok else {},
                error=item.error,
            )
        )

    existing = {row.canonical_url: row for row in db.scalars(
        select(SitemapEntry).where(SitemapEntry.site_id == site_id)
    ).all()}
    for entry in result["entries"]:
        row = existing.get(entry["canonical_url"])
        if row is None:
            db.add(
                SitemapEntry(
                    site_id=site_id,
                    loc=entry["loc"],
                    canonical_url=entry["canonical_url"],
                    lastmod=entry["lastmod"],
                    changefreq=entry["changefreq"],
                    priority=entry["priority"],
                    source_file=entry["source_file"],
                    is_gap=entry["is_gap"],
                )
            )
        else:
            row.loc = entry["loc"]
            row.lastmod = entry["lastmod"]
            row.changefreq = entry["changefreq"]
            row.priority = entry["priority"]
            row.source_file = entry["source_file"]
            row.is_gap = entry["is_gap"]
    removed = [canonical for canonical, action in result["actions"].items() if action == ACTION_REMOVED]
    for canonical in removed:
        row = existing.get(canonical)
        if row is not None:
            db.delete(row)

    round_row.note = (
        f"轮次 {round_row.round_no}：{result['stats']['total']} 条生效地址，"
        f"新增 {result['stats']['added']} / 更新 {result['stats']['updated']} / "
        f"沿用缺口 {result['stats']['reused_gap']} / 下线 {len(removed)}"
    )
    db.flush()
    return round_row


def sync_from_payload(
    db: Session,
    site: Site,
    payload_sources: list[dict],
    *,
    triggered_by: str = "manual",
) -> SitemapRound:
    """按调用方给出的拉取结果同步（API/演示/测试入口）。

    payload_sources 元素：``{"source_file", "ok", "entries"?, "error"?}``。
    成功项的 content_hash 由条目内容计算；失败项不参与删除语义。
    """
    inputs: list[SourceInput] = []
    for item in sorted(payload_sources, key=lambda row: row["source_file"]):
        source_file = item["source_file"]
        ok = bool(item.get("ok", True))
        entries = item.get("entries") or []
        for row in entries:
            row.setdefault("source_file", source_file)
            if not row.get("canonical_url"):
                row["canonical_url"] = normalize_url(row.get("loc"))
        inputs.append(
            SourceInput(
                source_file=source_file,
                ok=ok,
                entries=entries,
                error=item.get("error"),
                content_hash=_fingerprint(entries) if ok else None,
                fetched_at=item.get("fetched_at"),
            )
        )
    return apply_round(db, site, inputs, triggered_by=triggered_by)


def sync_fixture_site(
    db: Session,
    site: Site,
    spec: dict,
    *,
    fail_sources: set[str] | None = None,
    triggered_by: str = "manual",
) -> SitemapRound:
    """从离线 fixture 拉一个站点的全部子清单并同步；``fail_sources`` 模拟超时。"""
    fail_sources = fail_sources or set()
    descriptors = discover_fixture_sources(spec)
    inputs: list[SourceInput] = []
    for descriptor in descriptors:
        source_file = descriptor["source_file"]
        if source_file in fail_sources:
            inputs.append(
                SourceInput(
                    source_file=source_file,
                    ok=False,
                    error="子清单拉取超时（模拟上游 504）",
                )
            )
            continue
        try:
            entries = read_fixture_source(spec, source_file)
        except (OSError, SitemapParseError) as exc:
            inputs.append(SourceInput(source_file=source_file, ok=False, error=str(exc)[:300]))
            continue
        inputs.append(
            SourceInput(
                source_file=source_file,
                ok=True,
                entries=entries,
                content_hash=_fingerprint(entries),
            )
        )
    return apply_round(db, site, inputs, triggered_by=triggered_by)


def latest_round(db: Session, site_id: int) -> SitemapRound | None:
    return db.scalar(
        select(SitemapRound).where(SitemapRound.site_id == site_id).order_by(SitemapRound.id.desc()).limit(1)
    )


def changed_since_snapshot(db: Session, site: Site, baseline_hashes: dict | None) -> bool:
    """站点最新一轮的子清单指纹相对巡检快照基线是否变化。"""
    round_row = latest_round(db, site.id)
    if round_row is None:
        return True
    if not baseline_hashes:
        return True
    return bool(diff_source_hashes(round_row.source_hashes or {}, baseline_hashes))


def select_affected_sites(db: Session, sites: list[Site]) -> list[Site]:
    """挑出自最近一次巡检快照后子清单发生变化的站点（含从未进过快照的站点）。"""
    # 当前 run 已 flush 但还没冻结快照（sitemap_round_ids 为空），不能作为基线；
    # JSON 列的 IS NOT NULL 在 SQLite/MySQL 上对空默认值口径不一致，这里在 Python 侧过滤。
    candidates = db.scalars(select(CrawlRun).order_by(CrawlRun.id.desc()).limit(20)).all()
    last_run = next((row for row in candidates if row.sitemap_round_ids), None)
    baseline: dict[int, dict] = {}
    if last_run is not None and last_run.sitemap_round_ids:
        for raw_site_id, round_id in (last_run.sitemap_round_ids or {}).items():
            round_row = db.get(SitemapRound, int(round_id))
            if round_row is not None:
                baseline[int(raw_site_id)] = round_row.source_hashes or {}
    affected = []
    for site in sites:
        if changed_since_snapshot(db, site, baseline.get(site.id)):
            affected.append(site)
    return affected


def serialize_source(source: SitemapSource) -> dict:
    return {
        "id": source.id,
        "site_id": source.site_id,
        "source_file": source.source_file,
        "source_url": source.source_url,
        "status": source.status,
        "last_error": source.last_error,
        "last_success_hash": source.last_success_hash,
        "last_success_at": source.last_success_at.isoformat() if source.last_success_at else None,
        "last_attempt_at": source.last_attempt_at.isoformat() if source.last_attempt_at else None,
    }


def serialize_round(round_row: SitemapRound) -> dict:
    return {
        "id": round_row.id,
        "site_id": round_row.site_id,
        "round_no": round_row.round_no,
        "status": round_row.status,
        "source_total": round_row.source_total,
        "source_failed": round_row.source_failed,
        "entry_total": round_row.entry_total,
        "gap_count": round_row.gap_count,
        "source_hashes": round_row.source_hashes or {},
        "stats": round_row.stats or {},
        "note": round_row.note,
        "triggered_by": round_row.triggered_by,
        "created_at": round_row.created_at.isoformat() if round_row.created_at else None,
    }
