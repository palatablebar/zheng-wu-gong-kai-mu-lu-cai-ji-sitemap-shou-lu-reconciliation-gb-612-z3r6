"""sitemap.xml 里的一个 <url> 条目（三向对账的 B 集合）。"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.models import Base
from src.utils.timeutil import utcnow


class SitemapEntry(Base):
    __tablename__ = "sitemap_entries"
    __table_args__ = (UniqueConstraint("site_id", "loc", name="uq_sitemap_site_loc"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    site_id: Mapped[int] = mapped_column(ForeignKey("sites.id", ondelete="CASCADE"), index=True)
    loc: Mapped[str] = mapped_column(String(300))
    canonical_url: Mapped[str] = mapped_column(String(300), index=True)
    lastmod: Mapped[str | None] = mapped_column(String(20), nullable=True)
    changefreq: Mapped[str | None] = mapped_column(String(20), nullable=True)
    priority: Mapped[float] = mapped_column(Float, default=0.8)
    source_file: Mapped[str] = mapped_column(String(120), default="sitemap.xml")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
