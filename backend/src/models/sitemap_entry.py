"""sitemap 生效地址（三向对账的 B 集合）。

一条记录是「该站点某个 canonical URL 当前生效的 sitemap 版本」，
由多份子清单经 ``sitemap_resolve`` 按 lastmod 裁决产生：
- ``source_file`` 保留胜出记录来自哪一份子清单；
- ``lastmod`` 保留胜出记录的最后修改时间，迟到的旧清单不能覆盖它；
- ``is_gap=True`` 表示所属子清单本轮拉取失败、地址沿用上一版（数据缺口），
  对账时不得把这类地址当成下线。
历史版本见 ``SitemapVersion``，轮次裁决留痕见 ``SitemapRound``。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.models import Base
from src.utils.timeutil import utcnow


class SitemapEntry(Base):
    __tablename__ = "sitemap_entries"
    __table_args__ = (
        UniqueConstraint("site_id", "canonical_url", name="uq_sitemap_site_canonical"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    site_id: Mapped[int] = mapped_column(ForeignKey("sites.id", ondelete="CASCADE"), index=True)
    loc: Mapped[str] = mapped_column(String(300))
    canonical_url: Mapped[str] = mapped_column(String(300), index=True)
    lastmod: Mapped[str | None] = mapped_column(String(20), nullable=True)
    changefreq: Mapped[str | None] = mapped_column(String(20), nullable=True)
    priority: Mapped[float] = mapped_column(Float, default=0.8)
    source_file: Mapped[str] = mapped_column(String(120), default="sitemap.xml", index=True)
    is_gap: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)
