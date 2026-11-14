"""审计动作 -> 中文标签。"""
from __future__ import annotations

ACTIONS: dict[str, str] = {
    "auth.login": "登录",
    "site.create": "登记站点",
    "site.update": "修改站点",
    "catalog.create": "登记目录条目",
    "crawl.create": "发起巡检",
    "crawl.complete": "巡检完成",
    "defect.review": "处理缺陷单",
    "export.defects": "导出缺陷清单",
    "export.sites": "导出站点覆盖表",
    "export.coverage": "导出覆盖率报表",
    "http.mutation": "写请求",
}
