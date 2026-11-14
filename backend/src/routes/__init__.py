"""路由聚合：统一 /api 前缀（Nginx 反代时剥掉 /api）。"""
from fastapi import APIRouter

from src.routes.audit import router as audit_router
from src.routes.auth import router as auth_router
from src.routes.catalog import router as catalog_router
from src.routes.crawl_runs import router as crawl_runs_router
from src.routes.defects import router as defects_router
from src.routes.exports import router as exports_router
from src.routes.health import router as health_router
from src.routes.overview import router as overview_router
from src.routes.sites import router as sites_router
from src.routes.sitemaps import router as sitemaps_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(auth_router)
api_router.include_router(overview_router)
api_router.include_router(sites_router)
api_router.include_router(catalog_router)
api_router.include_router(sitemaps_router)
api_router.include_router(crawl_runs_router)
api_router.include_router(defects_router)
api_router.include_router(exports_router)
api_router.include_router(audit_router)
