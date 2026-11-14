from __future__ import annotations

from pydantic import BaseModel, Field


class SitemapEntryIn(BaseModel):
    site_id: int = Field(ge=1)
    loc: str = Field(min_length=8, max_length=300, pattern=r"^https?://")
    canonical_url: str | None = Field(default=None, max_length=300)
    lastmod: str | None = Field(default=None, max_length=20, pattern=r"^\d{4}-\d{2}-\d{2}$")
    changefreq: str = Field(default="weekly", max_length=20)
    priority: float = Field(default=0.8, ge=0.0, le=1.0)
    source_file: str = Field(default="sitemap.xml", max_length=120)
