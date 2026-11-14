from __future__ import annotations

from fastapi import APIRouter

from src.config.database import ping_db
from src.config.settings import settings
from src.services.overview_service import worker_alive

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict:
    redis_ok = False
    try:
        import redis

        redis.Redis.from_url(settings.redis_url, socket_connect_timeout=2).ping()
        redis_ok = True
    except Exception:
        redis_ok = False
    db_ok = ping_db()
    return {
        "status": "ok" if db_ok else "degraded",
        "db": db_ok,
        "redis": redis_ok,
        "worker": worker_alive(),
        "service": settings.app_name,
    }
