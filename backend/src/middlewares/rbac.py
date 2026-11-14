"""权限依赖：principal_of 取当前用户，require_roles 生成角色白名单依赖。

未登录 -> 401；角色不在白名单 -> 403（真实 HTTP 状态，不靠前端隐藏）。
"""
from __future__ import annotations

from fastapi import Request

from src.constants.enums import Role
from src.utils.errors import AppError, forbidden


def principal_of(request: Request) -> dict:
    principal = getattr(request.state, "principal", None)
    if not principal:
        raise AppError("AUTH_MISSING", 401)
    return principal


def require_roles(*roles: str):
    def dependency(request: Request) -> dict:
        principal = principal_of(request)
        if principal["role"] not in roles:
            raise forbidden({"role": principal["role"], "allowed": list(roles)})
        return principal

    return dependency


READ_ROLES = (Role.ADMIN.value, Role.ANALYST.value, Role.VIEWER.value)
