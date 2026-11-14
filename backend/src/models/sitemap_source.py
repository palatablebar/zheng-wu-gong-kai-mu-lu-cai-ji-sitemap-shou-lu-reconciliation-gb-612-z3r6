"""sitemap 子清单登记与版本化拉取留痕。

- ``SitemapSource``：一个站点登记的一份子清单（sitemap index 里的一个 <sitemap>）。
- ``SitemapVersion``：该子清单每次到达的不可变快照（成功或失败都留痕）。
  失败轮不覆盖 ``last_success_hash``，裁决时沿用上一版并标缺口。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.models import Base
from src.utils.timeutil import utcnow


class SitemapSource(Base):
    __tablename__ = "sitemap_sources"
    __table_args__ = (
        UniqueConstraint("site_id", "source_file", name="uq_source_site_file"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    site_id: Mapped[int] = mapped_column(ForeignKey("sites.id", ondelete="CASCADE"), index=True)
    source_file: Mapped[str] = mapped_column(String(200))
    source_url: Mapped[str | None] = mapped_column(String(300), nullable=True)
    # ok / failed / stale_gap
    status: Mapped[str] = mapped_column(String(20), default="ok", index=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_success_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_attempt_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class SitemapVersion(Base):
    """子清单的一次到达记录：成功存内容指纹与条目，失败存错误，均不可变。"""

    __tablename__ = "sitemap_versions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("sitemap_sources.id", ondelete="CASCADE"), index=True)
    site_id: Mapped[int] = mapped_column(ForeignKey("sites.id", ondelete="CASCADE"), index=True)
    round_id: Mapped[int | None] = mapped_column(
        ForeignKey("sitemap_rounds.id", ondelete="SET NULL"), nullable=True, index=True
    )
    status: Mapped[str] = mapped_column(String(20), index=True)  # ok / failed
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    entry_count: Mapped[int] = mapped_column(Integer, default=0)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
