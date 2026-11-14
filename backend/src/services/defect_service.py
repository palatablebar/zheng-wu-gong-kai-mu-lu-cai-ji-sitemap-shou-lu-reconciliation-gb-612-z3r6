"""缺陷单服务：分类查询、证据链序列化、整改流转。"""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.constants.enums import (
    DEFECT_CATEGORY_LABELS,
    DEFECT_CATEGORY_ORDER,
    DEFECT_SEVERITY_LABELS,
    DEFECT_SEVERITY_ORDER,
    DEFECT_STATUS_LABELS,
    DEFECT_STATUS_ORDER,
)
from src.models.crawl_run import CrawlRun
from src.models.defect import Defect
from src.models.site import Site
from src.utils.errors import AppError
from src.utils.timeutil import iso_utc, utcnow


def serialize(defect: Defect, run_no: str | None = None, site_name: str | None = None) -> dict:
    return {
        "id": defect.id,
        "run_id": defect.run_id,
        "run_no": run_no,
        "site_id": defect.site_id,
        "site_code": defect.site_code,
        "site_name": site_name,
        "category": defect.category,
        "category_label": DEFECT_CATEGORY_LABELS.get(defect.category, defect.category),
        "severity": defect.severity,
        "severity_label": DEFECT_SEVERITY_LABELS.get(defect.severity, defect.severity),
        "url": defect.url,
        "canonical_url": defect.canonical_url,
        "column_name": defect.column_name,
        "title": defect.title,
        "summary": defect.summary,
        "status": defect.status,
        "status_label": DEFECT_STATUS_LABELS.get(defect.status, defect.status),
        "evidence": defect.evidence or {},
        "reviewer": defect.reviewer,
        "review_note": defect.review_note,
        "created_at": iso_utc(defect.created_at),
        "updated_at": iso_utc(defect.updated_at),
    }


def list_defects(
    db: Session,
    *,
    run_id: int | None = None,
    site_id: int | None = None,
    category: str | None = None,
    severity: str | None = None,
    status: str | None = None,
    q: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> dict:
    stmt = select(Defect)
    count_stmt = select(func.count()).select_from(Defect)
    for clause in (
        (Defect.run_id == run_id) if run_id else None,
        (Defect.site_id == site_id) if site_id else None,
        (Defect.category == category) if category else None,
        (Defect.severity == severity) if severity else None,
        (Defect.status == status) if status else None,
    ):
        if clause is not None:
            stmt = stmt.where(clause)
            count_stmt = count_stmt.where(clause)
    if q:
        like = f"%{q.strip()}%"
        search = Defect.url.ilike(like) | Defect.summary.ilike(like) | Defect.site_code.ilike(like)
        stmt = stmt.where(search)
        count_stmt = count_stmt.where(search)
    total = db.scalar(count_stmt) or 0
    rows = db.scalars(stmt.order_by(Defect.id.desc()).limit(limit).offset(offset)).all()
    run_nos = {run.id: run.run_no for run in db.scalars(select(CrawlRun)).all()}
    site_names = {site.id: site.name for site in db.scalars(select(Site)).all()}
    return {
        "items": [serialize(row, run_nos.get(row.run_id), site_names.get(row.site_id)) for row in rows],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


def get_defect(db: Session, defect_id: int) -> Defect:
    defect = db.get(Defect, defect_id)
    if defect is None:
        raise AppError("NOT_FOUND", 404, {"entity": "defect", "id": defect_id})
    return defect


def facets(db: Session, run_id: int | None = None) -> dict:
    """分类 / 严重度 / 状态的计数，供前端筛选条与总览复用。"""

    def counts(column) -> dict[str, int]:
        stmt = select(column, func.count()).group_by(column)
        if run_id:
            stmt = stmt.where(Defect.run_id == run_id)
        return {str(key): int(value) for key, value in db.execute(stmt).all()}

    category = counts(Defect.category)
    severity = counts(Defect.severity)
    status = counts(Defect.status)
    return {
        "category": [
            {"key": key, "label": DEFECT_CATEGORY_LABELS.get(key, key), "count": category.get(key, 0)}
            for key in DEFECT_CATEGORY_ORDER
        ],
        "severity": [
            {"key": key, "label": DEFECT_SEVERITY_LABELS.get(key, key), "count": severity.get(key, 0)}
            for key in DEFECT_SEVERITY_ORDER
        ],
        "status": [
            {"key": key, "label": DEFECT_STATUS_LABELS.get(key, key), "count": status.get(key, 0)}
            for key in DEFECT_STATUS_ORDER
        ],
    }


def review(db: Session, defect: Defect, *, status: str, note: str | None, reviewer: str) -> Defect:
    defect.status = status
    defect.review_note = note
    defect.reviewer = reviewer
    defect.updated_at = utcnow()
    db.flush()
    return defect
