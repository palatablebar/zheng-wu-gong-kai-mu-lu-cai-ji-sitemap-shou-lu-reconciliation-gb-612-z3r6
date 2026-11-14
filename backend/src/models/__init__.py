"""ORM 模型聚合导出（Base 用于 create_all）。"""
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


from src.models.user import User  # noqa: E402
from src.models.audit import AuditLog  # noqa: E402
from src.models.site import Site  # noqa: E402
from src.models.catalog_item import CatalogItem  # noqa: E402
from src.models.sitemap_entry import SitemapEntry  # noqa: E402
from src.models.crawl_run import CrawlRun  # noqa: E402
from src.models.defect import Defect  # noqa: E402

__all__ = [
    "Base",
    "User",
    "AuditLog",
    "Site",
    "CatalogItem",
    "SitemapEntry",
    "CrawlRun",
    "Defect",
]
