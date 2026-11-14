"""巡检轮次的 sitemap 口径快照。

一次巡检发起时，把当时各站点的生效 sitemap 地址（``SitemapEntry`` 裁决结果）
原样冻结一份：之后对账（算法 B）、覆盖率统计、CSV 导出全部读这张快照，
保证"对账、覆盖率和导出使用同一轮清单口径"——巡检之后即使又同步了新清单，
历史巡检的结论与导出也不会悄悄变化。
"""
from __future__ import annotations

from sqlalchemy import Boolean, Float, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.models import Base


class CrawlRunSitemap(Base):
    __tablename__ = "crawl_run_sitemaps"
    __table_args__ = (
        UniqueConstraint("run_id", "canonical_url", name="uq_run_sitemap_canonical"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("crawl_runs.id", ondelete="CASCADE"), index=True)
    site_id: Mapped[int] = mapped_column(ForeignKey("sites.id", ondelete="CASCADE"), index=True)
    loc: Mapped[str] = mapped_column(String(300))
    canonical_url: Mapped[str] = mapped_column(String(300), index=True)
    lastmod: Mapped[str | None] = mapped_column(String(20), nullable=True)
    changefreq: Mapped[str | None] = mapped_column(String(20), nullable=True)
    priority: Mapped[float] = mapped_column(Float, default=0.8)
    source_file: Mapped[str] = mapped_column(String(120), default="sitemap.xml")
    is_gap: Mapped[bool] = mapped_column(Boolean, default=False)
