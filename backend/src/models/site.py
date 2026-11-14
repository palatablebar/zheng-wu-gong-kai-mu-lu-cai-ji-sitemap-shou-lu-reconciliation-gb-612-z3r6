"""政务站点：3 个政务站的可检索性登记（栏目 / sitemap / 分页口径）。"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.models import Base
from src.utils.timeutil import utcnow

DEFAULT_DEPT = "河州市政务公开办 · 网站编辑部"


class Site(Base):
    __tablename__ = "sites"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    home_url: Mapped[str] = mapped_column(String(200), default="")
    sitemap_url: Mapped[str] = mapped_column(String(200), default="")
    dept: Mapped[str] = mapped_column(String(120), default=DEFAULT_DEPT)
    region: Mapped[str] = mapped_column(String(40), default="市本级")
    page_size: Mapped[int] = mapped_column(Integer, default=12)
    max_depth: Mapped[int] = mapped_column(Integer, default=3)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    config: Mapped[dict] = mapped_column(JSON, default=dict)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    last_crawled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)
