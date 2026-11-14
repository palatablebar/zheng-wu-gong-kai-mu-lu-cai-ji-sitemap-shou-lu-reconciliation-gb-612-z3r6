from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class CrawlRunIn(BaseModel):
    site_id: int | None = Field(default=None, ge=1)
    trigger: Literal["manual", "schedule", "seed"] = "manual"
    params: dict = Field(default_factory=dict)
    # 增量巡检：只重算自上一轮快照后子清单发生变化的站点，其余沿用上一轮指标
    incremental: bool = False


class DefectReviewIn(BaseModel):
    status: Literal["pending", "fixed", "ignored"]
    note: str | None = Field(default=None, max_length=1000)
