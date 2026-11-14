"""分页与排序参数。"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Page:
    limit: int
    offset: int

    @property
    def size(self) -> int:
        return self.limit


def page_params(limit: int = 20, offset: int = 0) -> Page:
    limit = max(1, min(int(limit), 200))
    offset = max(0, int(offset))
    return Page(limit=limit, offset=offset)


def sort_clause(model, sort: str | None, allowed: dict[str, object], default: object, desc: bool = True):
    column = allowed.get(sort or "", default)
    return column.desc() if desc else column.asc()
