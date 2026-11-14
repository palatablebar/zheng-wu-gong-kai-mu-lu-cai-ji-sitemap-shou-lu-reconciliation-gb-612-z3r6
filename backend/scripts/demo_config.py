"""seed 侧入口：演示账号与三个政务站的巡检口径。

数据本体在 `src/constants/demo_data.py`（算法、fixture 生成与测试共用同一份口径），
这里只做再导出，保证 `scripts.seed_demo` 的引用路径稳定。
"""
from src.constants.demo_data import (  # noqa: F401
    BRAND_SHORT,
    COLUMNS,
    COLUMN_NAMES,
    DEMO_PASSWORD,
    DEMO_USERS,
    ORG,
    PAGE_SIZE,
    SEED_RUN_KEY,
    SEED_RUN_OPERATOR,
    SEED_RUN_SITE,
    SITES,
    TITLE_PATTERNS,
    WORDS,
)

__all__ = [
    "BRAND_SHORT",
    "COLUMNS",
    "COLUMN_NAMES",
    "DEMO_PASSWORD",
    "DEMO_USERS",
    "ORG",
    "PAGE_SIZE",
    "SEED_RUN_KEY",
    "SEED_RUN_OPERATOR",
    "SEED_RUN_SITE",
    "SITES",
    "TITLE_PATTERNS",
    "WORDS",
]
