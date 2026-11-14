"""一次巡检运行：分页抓取 + 三向对账的完整留痕。"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.models import Base
from src.utils.timeutil import utcnow


class CrawlRun(Base):
    __tablename__ = "crawl_runs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    run_no: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    site_id: Mapped[int | None] = mapped_column(ForeignKey("sites.id", ondelete="SET NULL"), nullable=True, index=True)
    trigger: Mapped[str] = mapped_column(String(20), default="manual")
    status: Mapped[str] = mapped_column(String(20), default="queued", index=True)
    operator_email: Mapped[str] = mapped_column(String(160), default="system")

    pages: Mapped[int] = mapped_column(Integer, default=0)
    links: Mapped[int] = mapped_column(Integer, default=0)
    unique_links: Mapped[int] = mapped_column(Integer, default=0)
    dup_ratio: Mapped[float] = mapped_column(Float, default=0.0)
    depth_max: Mapped[int] = mapped_column(Integer, default=0)
    sitemap_count: Mapped[int] = mapped_column(Integer, default=0)
    catalog_count: Mapped[int] = mapped_column(Integer, default=0)

    coverage: Mapped[float] = mapped_column(Float, default=0.0)
    unreachable_rate: Mapped[float] = mapped_column(Float, default=0.0)
    defect_count: Mapped[int] = mapped_column(Integer, default=0)
    p0_count: Mapped[int] = mapped_column(Integer, default=0)
    p1_count: Mapped[int] = mapped_column(Integer, default=0)
    p2_count: Mapped[int] = mapped_column(Integer, default=0)

    metrics: Mapped[dict] = mapped_column(JSON, default=dict)
    log_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    seed_key: Mapped[str | None] = mapped_column(String(120), unique=True, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
