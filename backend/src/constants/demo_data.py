"""演示账号、三个政务站与巡检口径（seed 与 fixture 生成的唯一数据源；放在 src 内便于算法与测试共用）。

数量口径（README「seed 数量口径」同步）：
- 3 个站点，每站 6 个栏目、120 条目录条目 → 目录 360 条
- 每站 12 个分页清单页（page_size=12）
- 3 份 sitemap.xml：362 条 loc，其中 14 条死链（404）
- 1 次巡检 → 31 条缺陷（P0 14 / P1 12 / P2 5）
"""

DEMO_PASSWORD = "Demo@2026"
BRAND_SHORT = "sitemapwatch"

ORG = "河州市政务公开办 · 网站编辑部"

DEMO_USERS = [
    ("admin@sitemapwatch.io", "沈书言 · 编辑部主管", "admin"),
    ("analyst@sitemapwatch.io", "陆知行 · 巡检专员", "analyst"),
    ("viewer@sitemapwatch.io", "何应秋 · 公开办审阅", "viewer"),
]

PAGE_SIZE = 12

# (栏目 code, 栏目名, 条目数) —— 每站 6 栏 × 合计 120 条
COLUMNS: list[tuple[str, str, int]] = [
    ("zcwj", "政策文件", 36),
    ("czjs", "财政预决算", 24),
    ("zdxm", "重大项目", 20),
    ("rsrm", "人事任免", 16),
    ("yjgl", "应急管理", 14),
    ("hjbh", "环境保护", 10),
]

COLUMN_NAMES: dict[str, str] = {code: name for code, name, _ in COLUMNS}

TITLE_PATTERNS: dict[str, list[str]] = {
    "zcwj": [
        "关于印发《河州市{w}管理办法》的通知",
        "关于做好{w}工作的通知",
        "《河州市{w}实施细则》政策解读",
        "市政府办公室关于{w}的实施意见",
    ],
    "czjs": [
        "河州市{w}部门预算公开表",
        "2026 年{w}财政决算说明",
        "关于下达{w}专项转移支付的通知",
    ],
    "zdxm": [
        "河州市{w}项目审批前公示",
        "{w}工程竣工环境保护验收公示",
        "重点项目{w}进展情况通报",
    ],
    "rsrm": [
        "关于{w}同志任免职的通知",
        "河州市公开选调{w}岗位公告",
        "关于{w}等 3 名同志任职的公示",
    ],
    "yjgl": [
        "河州市{w}应急预案（2026 修订）",
        "关于开展{w}应急演练的通知",
        "关于启动{w}应急响应的公告",
    ],
    "hjbh": [
        "河州市{w}环境质量月报",
        "关于{w}生态修复项目的公示",
        "重点排污单位{w}监测结果公开",
    ],
}

WORDS: dict[str, list[str]] = {
    "zcwj": ["政务公开", "政府投资", "公共资源交易", "政务服务", "行政许可", "行政执法"],
    "czjs": ["教育", "社会保障", "农林水", "交通运输", "卫生健康"],
    "zdxm": ["城市更新", "智慧交通", "供水管网", "污水处理", "安置房"],
    "rsrm": ["公开办", "信息中心", "督查室", "政务服务中心"],
    "yjgl": ["防汛防台", "低温雨雪", "地质灾害", "森林火灾"],
    "hjbh": ["大气", "地表水", "土壤", "噪声"],
}


def _item_range(column_code: str) -> int:
    for code, _, size in COLUMNS:
        if code == column_code:
            return size
    return 0


def _dead(count: int, column_code: str, start: int = 501) -> list[str]:
    return [f"/xxgk/{column_code}/{column_code}-{start + index:03d}.html" for index in range(count)]


def _missing(column_code: str, size: int, count: int) -> list[tuple[str, int]]:
    """该栏目最后 count 条已发布但不在 sitemap 中。"""
    last = _item_range(column_code)
    start = max(1, last - count + 1)
    return [(column_code, number) for number in range(start, min(last, start + count - 1) + 1)]


SITES: list[dict] = [
    {
        "code": "zwgk-hezhou",
        "name": "河州市人民政府 · 政务公开专栏",
        "home_url": "https://zwgk.hezhou.gov.cn",
        "sitemap_url": "https://zwgk.hezhou.gov.cn/sitemap.xml",
        "dept": "市政府办公室 · 政务公开科",
        "region": "市本级",
        "note": "主站，栏目最多、分页最深，季度巡检重点；人事任免栏目缺 rel=next，靠页码猜解。",
        "missing": _missing("zcwj", 36, 5),
        "dead": _dead(6, "zcwj"),
        "redirects": {
            "/xxgk/zcwj/zcwj-003.html": "/xxgk/zcwj/zcwj-013.html",
            "/xxgk/rsrm/rsrm-005.html": "/xxgk/rsrm/rsrm-015.html",
        },
        "canonical_mismatch": {},
        "no_rel_next": ["rsrm"],
    },
    {
        "code": "zwfw-hezhou",
        "name": "河州市政务服务网 · 公开目录",
        "home_url": "https://zwfw.hezhou.gov.cn",
        "sitemap_url": "https://zwfw.hezhou.gov.cn/sitemap.xml",
        "dept": "市政务服务管理办公室 · 信息公开处",
        "region": "市本级",
        "note": "与政务公开专栏共用稿源，财政预决算与重大项目两个栏目存在 canonical 口径问题。",
        "missing": _missing("czjs", 24, 4),
        "dead": _dead(5, "czjs"),
        "redirects": {"/xxgk/czjs/czjs-002.html": "/xxgk/czjs/czjs-012.html"},
        "canonical_mismatch": {
            "/xxgk/zdxm/zdxm-004.html": "/xxgk/zdxm/",
            "/xxgk/yjgl/yjgl-007.html": "/xxgk/yjgl/yjgl-008.html",
        },
        "no_rel_next": ["zdxm"],
    },
    {
        "code": "quxian-hezhou",
        "name": "河州市政务公开 · 区县专栏",
        "home_url": "https://quxian.hezhou.gov.cn",
        "sitemap_url": "https://quxian.hezhou.gov.cn/sitemap.xml",
        "dept": "区县政府办公室 · 政务信息股",
        "region": "区县",
        "note": "区县子站，采用独立 sitemap 生成脚本；重大项目栏目分页无 rel=next。",
        "missing": _missing("zdxm", 20, 3),
        "dead": _dead(3, "zdxm"),
        "redirects": {},
        "canonical_mismatch": {},
        "no_rel_next": ["yjgl"],
    },
]

SEED_RUN_KEY = "seed-crawl-2026q4"
SEED_RUN_SITE = None  # None = 全部启用站点
SEED_RUN_OPERATOR = "analyst@sitemapwatch.io"
