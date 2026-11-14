"""Celery 入口：backend 投递任务，worker 容器消费（心跳 + 每日重算）。"""
from __future__ import annotations

from celery import Celery
from celery.schedules import crontab

from src.config.settings import settings

TASK_HEARTBEAT = f"{settings.app_name}.heartbeat"
TASK_DAILY = f"{settings.app_name}.daily_refresh"

celery_app = Celery(
    settings.app_name,
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["src.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="Asia/Shanghai",
    enable_utc=False,
    task_track_started=True,
    result_expires=3600,
    broker_connection_retry_on_startup=True,
    worker_hijack_root_logger=False,
)

celery_app.conf.beat_schedule = {
    f"{settings.app_name}-heartbeat": {"task": TASK_HEARTBEAT, "schedule": 10.0},
    f"{settings.app_name}-daily": {"task": TASK_DAILY, "schedule": crontab(hour=7, minute=40)},
}
