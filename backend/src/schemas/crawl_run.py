from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class CrawlRunIn(BaseModel):
    site_id: int | None = Field(default=None, ge=1)
    trigger: Literal["manual", "schedule", "seed"] = "manual"
    params: dict = Field(default_factory=dict)


class DefectReviewIn(BaseModel):
    status: Literal["pending", "fixed", "ignored"]
    note: str | None = Field(default=None, max_length=1000)
