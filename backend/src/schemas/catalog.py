from __future__ import annotations

from pydantic import BaseModel, Field


class CatalogItemIn(BaseModel):
    site_id: int = Field(ge=1)
    column_code: str = Field(default="other", min_length=2, max_length=60, pattern=r"^[a-z0-9][a-z0-9_-]*$")
    column_name: str = Field(default="其他栏目", max_length=120)
    entry_url: str = Field(min_length=8, max_length=300, pattern=r"^https?://")
    canonical_url: str | None = Field(default=None, max_length=300)
    page_no: int = Field(default=1, ge=1, le=500)
    item_no: int = Field(default=0, ge=0, le=5000)
    depth: int = Field(default=2, ge=1, le=5)
    discovered_from: str = Field(default="rel_next", max_length=20)
    title: str = Field(default="", max_length=200)
    enabled: bool = True
