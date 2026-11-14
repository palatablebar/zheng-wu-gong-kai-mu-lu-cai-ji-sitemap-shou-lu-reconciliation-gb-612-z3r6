from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class ApiError(BaseModel):
    code: str
    message: str
    detail: Any | None = None


class HealthOut(BaseModel):
    status: str
    db: bool
    redis: bool
    worker: bool
    service: str


class PageOut(BaseModel):
    items: list[dict]
    total: int
    limit: int
    offset: int
