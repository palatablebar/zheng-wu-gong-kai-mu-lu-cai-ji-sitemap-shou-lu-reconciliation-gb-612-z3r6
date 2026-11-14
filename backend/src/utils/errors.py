"""统一业务异常：{code, message, detail}。"""
from __future__ import annotations

ERROR_MESSAGES: dict[str, str] = {
    "AUTH_MISSING": "请先登录",
    "AUTH_INVALID": "账号或密码不正确",
    "FORBIDDEN": "当前角色没有该操作权限",
    "NOT_FOUND": "资源不存在",
    "VALIDATION": "请求参数不合法",
    "CONFLICT": "数据冲突，请刷新后重试",
    "RATE_LIMITED": "请求过于频繁，请稍后再试",
    "INTERNAL": "服务内部错误",
}


class AppError(Exception):
    def __init__(self, code: str, status_code: int = 400, detail: dict | None = None, message: str | None = None):
        self.code = code
        self.status_code = status_code
        self.detail = detail or {}
        self.message = message or ERROR_MESSAGES.get(code, code)
        super().__init__(self.message)


def bad_request(code: str = "VALIDATION", detail: dict | None = None) -> AppError:
    return AppError(code, 400, detail)


def not_found(entity: str, entity_id: object = None) -> AppError:
    return AppError("NOT_FOUND", 404, {"entity": entity, "id": entity_id})


def forbidden(detail: dict | None = None) -> AppError:
    return AppError("FORBIDDEN", 403, detail)
