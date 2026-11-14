"""共享枚举（后端唯一定义处）。前端副本见 frontend/site/js/config.js。

README「共享枚举出现位置」一节列出全部出现点，改动需两侧同步。
"""
from __future__ import annotations

from enum import StrEnum


class Role(StrEnum):
    ADMIN = "admin"
    ANALYST = "analyst"
    VIEWER = "viewer"


class CrawlStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"


CRAWL_STATUS_LABELS: dict[str, str] = {
    CrawlStatus.QUEUED.value: "排队中",
    CrawlStatus.RUNNING.value: "抓取中",
    CrawlStatus.SUCCESS.value: "完成",
    CrawlStatus.PARTIAL.value: "部分完成",
    CrawlStatus.FAILED.value: "失败",
}

CRAWL_STATUS_ORDER: list[str] = [
    CrawlStatus.QUEUED.value,
    CrawlStatus.RUNNING.value,
    CrawlStatus.SUCCESS.value,
    CrawlStatus.PARTIAL.value,
    CrawlStatus.FAILED.value,
]


class TriggerKind(StrEnum):
    MANUAL = "manual"
    SCHEDULE = "schedule"
    SEED = "seed"


TRIGGER_LABELS: dict[str, str] = {
    TriggerKind.MANUAL.value: "手动巡检",
    TriggerKind.SCHEDULE.value: "定时巡检",
    TriggerKind.SEED.value: "初始化巡检",
}


class DiscoverySource(StrEnum):
    """分页入口的发现方式（算法 A 的发现来源标记）。"""

    HOME_LINK = "home_link"
    REL_NEXT = "rel_next"
    INDEX_GUESS = "index_guess"
    SITEMAP_PROBE = "sitemap_probe"


DISCOVERY_LABELS: dict[str, str] = {
    DiscoverySource.HOME_LINK.value: "首页链接",
    DiscoverySource.REL_NEXT.value: "rel=next",
    DiscoverySource.INDEX_GUESS.value: "页码猜解",
    DiscoverySource.SITEMAP_PROBE.value: "sitemap 探测",
}


class DefectCategory(StrEnum):
    """三向对账的缺陷分类（算法 B）。"""

    ONLY_IN_CATALOG = "only_in_catalog"          # 目录有、sitemap 没有
    ONLY_IN_SITEMAP_DEAD = "only_in_sitemap_dead"  # sitemap 有、但探测 404
    REDIRECT_CHAIN = "redirect_chain"            # 入口 301 链路
    CANONICAL_MISMATCH = "canonical_mismatch"    # rel=canonical 与自身不一致
    DUPLICATE_SLUG = "duplicate_slug"            # 多个原始 URL 归一后撞车


DEFECT_CATEGORY_LABELS: dict[str, str] = {
    DefectCategory.ONLY_IN_CATALOG.value: "目录有·sitemap 未收录",
    DefectCategory.ONLY_IN_SITEMAP_DEAD.value: "sitemap 死链",
    DefectCategory.REDIRECT_CHAIN.value: "重定向链路",
    DefectCategory.CANONICAL_MISMATCH.value: "canonical 不一致",
    DefectCategory.DUPLICATE_SLUG.value: "重复 slug",
}

DEFECT_CATEGORY_ORDER: list[str] = [
    DefectCategory.ONLY_IN_SITEMAP_DEAD.value,
    DefectCategory.ONLY_IN_CATALOG.value,
    DefectCategory.REDIRECT_CHAIN.value,
    DefectCategory.CANONICAL_MISMATCH.value,
    DefectCategory.DUPLICATE_SLUG.value,
]


class DefectSeverity(StrEnum):
    P0 = "p0"
    P1 = "p1"
    P2 = "p2"


DEFECT_SEVERITY_LABELS: dict[str, str] = {
    DefectSeverity.P0.value: "P0 阻断",
    DefectSeverity.P1.value: "P1 漏收",
    DefectSeverity.P2.value: "P2 待优化",
}

DEFECT_SEVERITY_ORDER: list[str] = [DefectSeverity.P0.value, DefectSeverity.P1.value, DefectSeverity.P2.value]

# 严重度由分类决定：死链 P0、漏收 P1、链路/口径 P2
CATEGORY_SEVERITY: dict[str, str] = {
    DefectCategory.ONLY_IN_SITEMAP_DEAD.value: DefectSeverity.P0.value,
    DefectCategory.ONLY_IN_CATALOG.value: DefectSeverity.P1.value,
    DefectCategory.DUPLICATE_SLUG.value: DefectSeverity.P1.value,
    DefectCategory.REDIRECT_CHAIN.value: DefectSeverity.P2.value,
    DefectCategory.CANONICAL_MISMATCH.value: DefectSeverity.P2.value,
}


class DefectStatus(StrEnum):
    PENDING = "pending"
    FIXED = "fixed"
    IGNORED = "ignored"


DEFECT_STATUS_LABELS: dict[str, str] = {
    DefectStatus.PENDING.value: "待整改",
    DefectStatus.FIXED.value: "已整改",
    DefectStatus.IGNORED.value: "已忽略",
}

DEFECT_STATUS_ORDER: list[str] = [
    DefectStatus.PENDING.value,
    DefectStatus.FIXED.value,
    DefectStatus.IGNORED.value,
]
