"""sitemap 同步轮次：一次多子清单拉取 + 裁决的完整留痕。

一轮 = 对一个站点的全部登记子清单拉取一次，并按 lastmod 裁决出生效地址。
- 任一子清单失败 → ``status=partial``，失败源沿用上一版（缺口计入 ``gap_count``）；
- ``source_hashes`` 记录本轮子清单内容指纹，下一轮用它判断"单文件变化"，
  只把受影响站点交给巡检重算；
- ``stats`` 记录 added/updated/kept/reused/removed 计数，审计可回放。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.models import Base
from src.utils.timeutil import utcnow


class SitemapRound(Base):
    __tablename__ = "sitemap_rounds"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    site_id: Mapped[int] = mapped_column(ForeignKey("sites.id", ondelete="CASCADE"), index=True)
    round_no: Mapped[str] = mapped_column(String(40), index=True)
    # success / partial / failed
    status: Mapped[str] = mapped_column(String(20), default="success", index=True)
    source_total: Mapped[int] = mapped_column(Integer, default=0)
    source_failed: Mapped[int] = mapped_column(Integer, default=0)
    entry_total: Mapped[int] = mapped_column(Integer, default=0)
    gap_count: Mapped[int] = mapped_column(Integer, default=0)
    source_hashes: Mapped[dict] = mapped_column(JSON, default=dict)
    stats: Mapped[dict] = mapped_column(JSON, default=dict)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    triggered_by: Mapped[str] = mapped_column(String(160), default="system")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
