"""子清单裁决纯函数：同一地址按 lastmod 选版本，失败源沿用上一版并标出缺口。

背景：政务站把 sitemap 拆成多份子清单后，季度核对会遇到两类误判——
1. 后到的旧清单直接覆盖已生效地址（没有按 lastmod 裁决）；
2. 某个子清单超时，剩余地址被当成全部下线（失败态被当成"空清单"）。

本模块不碰数据库、不碰网络，只描述裁决口径，方便单测固化：
- 地址身份用归一后的 canonical URL（与算法 A/B 同一套 normalize_url）；
- 同一地址出现多份记录时，lastmod 更晚的胜出；lastmod 相等时来源顺序靠前的胜出；
  都没有 lastmod 时保持先到者；
- 失败（超时/解析失败）的子清单不参与"删除语义"，其地址沿用上一版，
  仅在结果里以 gap 标出，调用方不得把这些地址判成下线。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from src.services.url_normalize import normalize_url

# 源/轮次级状态
SOURCE_OK = "ok"
SOURCE_FAILED = "failed"          # 本轮拉取失败（超时/HTTP 错误/解析失败）
SOURCE_STALE_GAP = "stale_gap"    # 失败后沿用上一版，存在数据缺口

ROUND_SUCCESS = "success"
ROUND_PARTIAL = "partial"          # 至少一个子清单失败、沿用了旧版

# 单条地址的裁决动作
ACTION_ADDED = "added"            # 新地址
ACTION_UPDATED = "updated"        # lastmod 更晚，新版本替换旧版本
ACTION_KEPT = "kept"              # 平局或更旧，保留已生效版本
ACTION_REUSED = "reused"          # 来源失败，沿用上一版地址
ACTION_REMOVED = "removed"        # 来源成功且新版不再包含该地址


def parse_lastmod(value: str | None) -> date | None:
    """sitemap lastmod 支持 W3C 日期或日期时间，统一裁成 date 比较。"""
    if not value:
        return None
    text = str(value).strip()
    if not text:
        return None
    head = text[:10]
    try:
        return date.fromisoformat(head)
    except ValueError:
        return None


def _is_newer(incoming: str | None, current: str | None) -> bool:
    """incoming 的 lastmod 是否应替换 current。

    - 两侧都有日期：严格更晚才更新；
    - 当前版本缺 lastmod、新记录带有效日期：新记录信息更全，允许更新；
    - 新记录缺 lastmod：永远不覆盖（无法证明它更新）。
    """
    incoming_date = parse_lastmod(incoming)
    current_date = parse_lastmod(current)
    if incoming_date is None:
        return False
    if current_date is None:
        return True
    return incoming_date > current_date


@dataclass
class SourceInput:
    """一轮同步中某个子清单的拉取结果。"""

    source_file: str
    ok: bool
    entries: list[dict] = field(default_factory=list)
    error: str | None = None
    content_hash: str | None = None
    fetched_at: str | None = None


@dataclass
class ResolvedEntry:
    canonical_url: str
    loc: str
    lastmod: str | None
    source_file: str
    changefreq: str | None
    priority: float
    is_gap: bool
    action: str


def _entry_key(entry: dict) -> str:
    return normalize_url(entry.get("canonical_url") or entry.get("loc"))


def resolve_round(
    sources: list[SourceInput],
    previous: dict[str, dict] | None = None,
) -> dict:
    """裁决一轮多子清单同步。

    参数
    ----
    sources: 本轮各子清单的拉取结果（顺序即来源优先级，平局时靠前者胜）。
    previous: 上一版生效地址，键为 canonical URL，值至少含
              ``loc/lastmod/source_file/changefreq/priority``。

    返回
    ----
    ``{entries, by_canonical, gaps, failed_sources, stats, actions}``：
    - entries: 裁决后的生效地址（含来源、lastmod、是否缺口沿用）；
    - gaps: 因源失败而沿用上一版的 canonical URL 列表；
    - failed_sources: 失败的子清单文件名；
    - stats: 各类裁决动作计数与缺口数；
    - actions: canonical -> 动作，便于审计与"只重算受影响站点"。
    """
    previous = previous or {}
    winners: dict[str, ResolvedEntry] = {}
    # 记录每个 canonical 当前赢家在 sources 中的次序，用于平局裁决
    winner_order: dict[str, int] = {}
    failed_sources: list[str] = []
    gaps: set[str] = set()
    actions: dict[str, str] = {}

    # 1) 先处理成功到达的子清单：同地址按 lastmod 裁决，迟到的旧记录不能覆盖新记录
    for order, source in enumerate(sources):
        if not source.ok:
            failed_sources.append(source.source_file)
            continue
        seen_in_source: set[str] = set()
        for raw in source.entries:
            canonical = _entry_key(raw)
            if not canonical or canonical in seen_in_source:
                continue
            seen_in_source.add(canonical)
            lastmod = raw.get("lastmod")
            current = winners.get(canonical)
            if current is None:
                old = previous.get(canonical)
                if old is not None and not _is_newer(lastmod, old.get("lastmod")):
                    # 迟到清单里的记录并不比已生效版本新 → 保留已生效版本
                    winners[canonical] = ResolvedEntry(
                        canonical_url=canonical,
                        loc=old.get("loc") or raw.get("loc"),
                        lastmod=old.get("lastmod"),
                        source_file=old.get("source_file") or source.source_file,
                        changefreq=old.get("changefreq"),
                        priority=float(old.get("priority") or 0.8),
                        is_gap=False,
                        action=ACTION_KEPT,
                    )
                    winner_order[canonical] = order
                    actions[canonical] = ACTION_KEPT
                else:
                    winners[canonical] = ResolvedEntry(
                        canonical_url=canonical,
                        loc=raw.get("loc"),
                        lastmod=lastmod,
                        source_file=source.source_file,
                        changefreq=raw.get("changefreq"),
                        priority=float(raw.get("priority") or 0.8),
                        is_gap=False,
                        action=ACTION_ADDED if old is None else ACTION_UPDATED,
                    )
                    winner_order[canonical] = order
                    actions[canonical] = ACTION_ADDED if old is None else ACTION_UPDATED
                continue
            # 同一轮内多个子清单声明同一地址
            if _is_newer(lastmod, current.lastmod):
                winners[canonical] = ResolvedEntry(
                    canonical_url=canonical,
                    loc=raw.get("loc"),
                    lastmod=lastmod,
                    source_file=source.source_file,
                    changefreq=raw.get("changefreq"),
                    priority=float(raw.get("priority") or 0.8),
                    is_gap=False,
                    action=ACTION_UPDATED,
                )
                winner_order[canonical] = order
                actions[canonical] = ACTION_UPDATED
            elif parse_lastmod(lastmod) == parse_lastmod(current.lastmod) and order < winner_order[canonical]:
                # lastmod 相同：来源顺序优先（确定性），不算更新
                winner_order[canonical] = order

    # 2) 失败子清单沿用上一版：不参与删除，只标缺口
    failed_set = set(failed_sources)
    if failed_set:
        for canonical, old in previous.items():
            if canonical in winners:
                continue
            if old.get("source_file") not in failed_set:
                continue
            winners[canonical] = ResolvedEntry(
                canonical_url=canonical,
                loc=old.get("loc"),
                lastmod=old.get("lastmod"),
                source_file=old.get("source_file"),
                changefreq=old.get("changefreq"),
                priority=float(old.get("priority") or 0.8),
                is_gap=True,
                action=ACTION_REUSED,
            )
            gaps.add(canonical)
            actions[canonical] = ACTION_REUSED
    # 3) 成功子清单已不再包含、且不属于失败源缺口的旧地址 → 正式下线
    for canonical, old in previous.items():
        if canonical in winners:
            continue
        if old.get("source_file") in failed_set:
            continue
        actions[canonical] = ACTION_REMOVED

    stats = {
        "total": len(winners),
        "added": sum(1 for value in actions.values() if value == ACTION_ADDED),
        "updated": sum(1 for value in actions.values() if value == ACTION_UPDATED),
        "kept": sum(1 for value in actions.values() if value == ACTION_KEPT),
        "reused_gap": len(gaps),
        "removed": sum(1 for value in actions.values() if value == ACTION_REMOVED),
        "failed_sources": len(failed_sources),
    }
    entries = [
        {
            "canonical_url": item.canonical_url,
            "loc": item.loc,
            "lastmod": item.lastmod,
            "source_file": item.source_file,
            "changefreq": item.changefreq,
            "priority": item.priority,
            "is_gap": item.is_gap,
            "action": item.action,
        }
        for item in sorted(winners.values(), key=lambda resolved: resolved.canonical_url)
    ]
    return {
        "entries": entries,
        "by_canonical": {item["canonical_url"]: item for item in entries},
        "gaps": sorted(gaps),
        "failed_sources": failed_sources,
        "status": ROUND_PARTIAL if failed_sources else ROUND_SUCCESS,
        "stats": stats,
        "actions": dict(sorted(actions.items())),
    }


def diff_source_hashes(current: dict[str, str], previous: dict[str, str] | None) -> list[str]:
    """对比两轮子清单内容指纹，返回发生变化的来源文件（含新增、消失）。

    用于"上游清单独文件变化后只重算受影响站点"：指纹不变的来源不触发重算。
    失败源在新一轮没有指纹（键消失），按"变化"处理，保证故障站点会被重算并标缺口。
    """
    previous = previous or {}
    names = set(current) | set(previous)
    changed = [source for source in sorted(names) if current.get(source) != previous.get(source)]
    return changed


def affected_canonicals(actions: dict[str, str], removed: set[str] | None = None) -> set[str]:
    """一轮裁决中真正发生变化的地址（新增/更新/删除），kept/reused 不算变化。"""
    touched = {
        canonical
        for canonical, action in actions.items()
        if action in (ACTION_ADDED, ACTION_UPDATED, ACTION_REMOVED)
    }
    if removed:
        touched |= set(removed)
    return touched
