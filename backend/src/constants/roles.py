"""角色 -> 权限点映射。README 与前端 site/js/config.js 同步。

角色键固定为 admin / analyst / viewer，各项目的展示名与职责不同。
"""
from __future__ import annotations

from src.constants.enums import Role

ROLE_LABELS: dict[str, str] = {
    Role.ADMIN.value: "编辑部主管",
    Role.ANALYST.value: "巡检专员",
    Role.VIEWER.value: "公开办审阅",
}

ROLE_DUTIES: dict[str, str] = {
    Role.ADMIN.value: "登记站点与栏目、发起巡检、导出报表、查看审计日志",
    Role.ANALYST.value: "发起巡检、处理缺陷单、提交整改进展",
    Role.VIEWER.value: "只读查看覆盖率和缺陷明细，不能发起巡检或导出",
}

PERMISSIONS: dict[str, set[str]] = {
    Role.ADMIN.value: {
        "site:read", "site:write",
        "catalog:read", "catalog:write",
        "sitemap:read",
        "crawl:read", "crawl:create",
        "defect:read", "defect:review",
        "export:read", "audit:read", "overview:read",
    },
    Role.ANALYST.value: {
        "site:read",
        "catalog:read",
        "sitemap:read",
        "crawl:read", "crawl:create",
        "defect:read", "defect:review",
        "export:read", "overview:read",
    },
    Role.VIEWER.value: {
        "site:read",
        "catalog:read",
        "sitemap:read",
        "crawl:read",
        "defect:read",
        "overview:read",
    },
}

SITE_WRITE_ROLES = (Role.ADMIN.value,)
CATALOG_WRITE_ROLES = (Role.ADMIN.value,)
CRAWL_CREATE_ROLES = (Role.ADMIN.value, Role.ANALYST.value)
DEFECT_REVIEW_ROLES = (Role.ADMIN.value, Role.ANALYST.value)
EXPORT_ROLES = (Role.ADMIN.value, Role.ANALYST.value)
AUDIT_ROLES = (Role.ADMIN.value,)
READ_ROLES = (Role.ADMIN.value, Role.ANALYST.value, Role.VIEWER.value)


def has_permission(role: str, permission: str) -> bool:
    return permission in PERMISSIONS.get(role, set())
