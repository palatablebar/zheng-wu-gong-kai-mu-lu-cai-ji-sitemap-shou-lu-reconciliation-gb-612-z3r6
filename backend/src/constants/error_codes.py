"""错误码与前端恢复动作。"""

ERROR_ACTIONS: dict[str, str] = {
    "AUTH_MISSING": "跳转登录",
    "AUTH_INVALID": "提示账号密码错误",
    "FORBIDDEN": "提示权限不足并保留当前页面",
    "NOT_FOUND": "回列表并提示资源已删除",
    "VALIDATION": "高亮非法字段",
    "CONFLICT": "提示刷新后重试",
    "RATE_LIMITED": "提示稍后重试并禁用提交按钮 3 秒",
    "INTERNAL": "展示可重试错误态",
}
