from __future__ import annotations

from pydantic import BaseModel, Field


class SitemapEntryIn(BaseModel):
    site_id: int = Field(ge=1)
    loc: str = Field(min_length=8, max_length=300, pattern=r"^https?://")
    canonical_url: str | None = Field(default=None, max_length=300)
    lastmod: str | None = Field(default=None, max_length=20, pattern=r"^\d{4}-\d{2}-\d{2}")
    changefreq: str = Field(default="weekly", max_length=20)
    priority: float = Field(default=0.8, ge=0.0, le=1.0)
    source_file: str = Field(default="manual.xml", max_length=120)


class SitemapSourceInput(BaseModel):
    """一份子清单的拉取结果。ok=False 时 entries 可空，error 写明失败原因。"""

    source_file: str = Field(min_length=1, max_length=200)
    ok: bool = True
    entries: list[dict] = Field(default_factory=list)
    error: str | None = Field(default=None, max_length=500)


class SitemapSyncIn(BaseModel):
    site_id: int = Field(ge=1)
    sources: list[SitemapSourceInput] = Field(min_length=1)


class FixtureSyncIn(BaseModel):
    site_id: int | None = Field(default=None, ge=1)
    # 模拟拉取超时的子清单文件名
    fail_sources: list[str] = Field(default_factory=list)
