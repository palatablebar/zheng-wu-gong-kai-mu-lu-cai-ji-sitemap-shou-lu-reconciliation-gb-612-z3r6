"""Celery 任务：心跳、每日巡检（对启用中的站点重跑一次三向对账）。"""
from __future__ import annotations

import time

from sqlalchemy import select

from src.config.celery_app import TASK_DAILY, TASK_HEARTBEAT, celery_app
from src.config.settings import settings
from src.utils.logger import get_logger

logger = get_logger("tasks")


def _redis():
    import redis

    return redis.Redis.from_url(settings.redis_url, decode_responses=True)


@celery_app.task(name=TASK_HEARTBEAT)
def heartbeat() -> str:
    try:
        _redis().set(f"{settings.app_name}:worker:heartbeat", time.time())
        return "ok"
    except Exception as exc:  # noqa: BLE001
        logger.warning("heartbeat failed: %s", exc)
        return "error"


@celery_app.task(name=TASK_DAILY)
def daily_refresh() -> dict:
    from src.config.database import session_scope
    from src.models.site import Site
    from src.services import audit_service, crawl_run_service

    done = 0
    with session_scope() as db:
        sites = db.scalars(select(Site).where(Site.enabled.is_(True)).order_by(Site.id)).all()
        if not sites:
            return {"sites": 0}
        run = crawl_run_service.create_and_execute(
            db,
            site_id=None,
            trigger="schedule",
            operator_email="scheduler@" + settings.app_name + ".io",
        )
        done = len(sites)
        audit_service.record(
            db,
            actor_email="scheduler@" + settings.app_name + ".io",
            actor_role="admin",
            action="crawl.create",
            entity="crawl_run",
            entity_id=run.id,
            detail={"trigger": "schedule", "run_no": run.run_no, "defects": run.defect_count},
            layer="worker",
        )
    logger.info("daily crawl finished: %s sites", done)
    return {"sites": done}
