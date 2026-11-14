/**
 * 项目品牌、导航、角色权限与枚举文案（前端唯一定义处）。
 * 后端对应：backend/src/constants/{roles,enums}.py + demo_data.py；README 列出全部出现位置。
 */
export const BRAND = {
  short: 'sitemapwatch',
  title: '政务公开目录采集与 sitemap 收录对账',
  org: '河州市政务公开办 · 网站编辑部',
  edition: 'ARCHIVE INDEX · 2026 Q4',
  subtitle: '3 个政务站 · 360 条公开目录 · 三向对账（目录 / sitemap / 可达）',
  loginLead: '栏目页有链接、sitemap 没收录，搜索引擎就抓不到；详情页下线了、sitemap 还指着 404。这份台账要能一条条指回原始 URL。',
  loginPoints: [
    ['01', '站点与栏目登记：栏目入口 canonical 一次登记，后续巡检按同一口径跑。'],
    ['02', '分页抓取：rel=next 优先，缺失时按 index_2.html 猜解，追踪参数与锚点先归一再计重。'],
    ['03', '三向对账：只查 sitemap 看不出漏收，三向对账才能把 P0 死链和 P1 漏收分开。'],
  ],
  catalogMark: 'ZWGK-2026-Q4',
  catalogLabels: ['三向对账', '季度巡检', '缺陷单闭环'],
};

export const NAV = [
  { to: '#/overview', no: '01', label: '总览', permission: 'overview:read' },
  { to: '#/sites', no: '02', label: '站点与栏目', permission: 'site:read' },
  { to: '#/crawl-runs', no: '03', label: '抓取运行', permission: 'crawl:read' },
  { to: '#/defects', no: '04', label: '对账缺陷', permission: 'defect:read' },
  { to: '#/reports', no: '05', label: '报表与导出', permission: 'defect:read' },
];

export const ROLE_LABELS = {
  admin: '编辑部主管',
  analyst: '巡检专员',
  viewer: '公开办审阅',
};

export const ROLE_DUTIES = {
  admin: '登记站点与栏目、发起巡检、导出报表、查看审计',
  analyst: '发起巡检、处理缺陷单、提交整改进展',
  viewer: '只读查看覆盖率与缺陷明细',
};

export const PERMISSIONS = {
  admin: [
    'overview:read', 'site:read', 'site:write', 'catalog:read', 'catalog:write', 'sitemap:read',
    'crawl:read', 'crawl:create', 'defect:read', 'defect:review', 'export:read', 'audit:read',
  ],
  analyst: [
    'overview:read', 'site:read', 'catalog:read', 'sitemap:read',
    'crawl:read', 'crawl:create', 'defect:read', 'defect:review', 'export:read',
  ],
  viewer: ['overview:read', 'site:read', 'catalog:read', 'sitemap:read', 'crawl:read', 'defect:read'],
};

export const ENUMS = {
  category: {
    only_in_catalog: '目录有·sitemap 未收录',
    only_in_sitemap_dead: 'sitemap 死链',
    redirect_chain: '重定向链路',
    canonical_mismatch: 'canonical 不一致',
    duplicate_slug: '重复 slug',
  },
  severity: {
    p0: 'P0 阻断',
    p1: 'P1 漏收',
    p2: 'P2 待优化',
  },
  defectStatus: {
    pending: '待整改',
    fixed: '已整改',
    ignored: '已忽略',
  },
  crawlStatus: {
    queued: '排队中',
    running: '抓取中',
    success: '完成',
    partial: '部分完成',
    failed: '失败',
  },
  trigger: {
    manual: '手动巡检',
    schedule: '定时巡检',
    seed: '初始化巡检',
  },
  discovery: {
    home_link: '首页链接',
    rel_next: 'rel=next',
    index_guess: '页码猜解',
    sitemap_probe: 'sitemap 探测',
  },
};

export const CATEGORY_TONE = {
  only_in_sitemap_dead: 'danger',
  only_in_catalog: 'warn',
  redirect_chain: 'info',
  canonical_mismatch: 'info',
  duplicate_slug: 'warn',
};

export function can(role, permission) {
  return (PERMISSIONS[role] || []).includes(permission);
}

export function badgeTone(severity) {
  return { p0: 'high', p1: 'medium', p2: 'low' }[severity] || 'info';
}

export function statusTone(status) {
  return { pending: 'pending warn', fixed: 'ok', ignored: 'info' }[status] || 'info';
}

export function crawlTone(status) {
  return { success: 'ok', partial: 'warn', failed: 'danger', running: 'info', queued: 'info' }[status] || 'info';
}
