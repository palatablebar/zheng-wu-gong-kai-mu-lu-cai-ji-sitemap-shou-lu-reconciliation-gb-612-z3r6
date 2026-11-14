from __future__ import annotations

from pydantic import BaseModel, Field

HOME_URL_PATTERN = r"^https://[a-z0-9][a-z0-9.\-]*\.[a-z]{2,}(:\d{2,5})?$"


class SiteIn(BaseModel):
    code: str = Field(min_length=2, max_length=40, pattern=r"^[a-z0-9][a-z0-9-]*$")
    name: str = Field(min_length=2, max_length=120)
    home_url: str = Field(min_length=8, max_length=200, pattern=HOME_URL_PATTERN)
    sitemap_url: str | None = Field(default=None, max_length=200)
    dept: str | None = Field(default=None, max_length=120)
    region: str = Field(default="市本级", max_length=40)
    page_size: int = Field(default=12, ge=1, le=100)
    max_depth: int = Field(default=3, ge=1, le=5)
    note: str | None = Field(default=None, max_length=2000)
    config: dict = Field(default_factory=dict)
    enabled: bool = True


class SitePatch(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    home_url: str | None = Field(default=None, min_length=8, max_length=200, pattern=HOME_URL_PATTERN)
    sitemap_url: str | None = Field(default=None, max_length=200)
    dept: str | None = Field(default=None, max_length=120)
    region: str | None = Field(default=None, max_length=40)
    page_size: int | None = Field(default=None, ge=1, le=100)
    max_depth: int | None = Field(default=None, ge=1, le=5)
    note: str | None = Field(default=None, max_length=2000)
    config: dict | None = None
    enabled: bool | None = None
