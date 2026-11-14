"""公开目录条目：栏目入口 / 详情页的 canonical URL 登记（三向对账的 A 集合）。"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.models import Base
from src.utils.timeutil import utcnow


class CatalogItem(Base):
    __tablename__ = "catalog_items"
    __table_args__ = (UniqueConstraint("site_id", "entry_url", name="uq_catalog_site_entry"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    site_id: Mapped[int] = mapped_column(ForeignKey("sites.id", ondelete="CASCADE"), index=True)
    column_code: Mapped[str] = mapped_column(String(60), index=True)
    column_name: Mapped[str] = mapped_column(String(120), default="")
    entry_url: Mapped[str] = mapped_column(String(300))
    canonical_url: Mapped[str] = mapped_column(String(300), index=True)
    page_no: Mapped[int] = mapped_column(Integer, default=1)
    item_no: Mapped[int] = mapped_column(Integer, default=0)
    depth: Mapped[int] = mapped_column(Integer, default=2)
    discovered_from: Mapped[str] = mapped_column(String(20), default="rel_next")
    title: Mapped[str] = mapped_column(String(200), default="")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
