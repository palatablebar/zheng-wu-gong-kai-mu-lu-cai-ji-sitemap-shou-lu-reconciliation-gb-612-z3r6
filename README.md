# 政务公开目录采集与 sitemap 收录对账（`sitemapwatch`）

> 数据工程 · 中型多模块项目。原生 HTML/CSS/JS 前端 + Python FastAPI 后端 + Celery worker + MySQL 8.0 + Redis，5 个容器一键起。

## 1. 场景

- **模拟客户**：河州市政务公开办 · 网站编辑部（6 人），负责 3 个政务站、约 2.4 万条主动公开信息的可检索性（本期纳入 360 条重点目录做季度巡检）。
- **现有工作流**：编辑手工点栏目、肉眼比对 sitemap.xml，季度巡检一次；发现问题后在微信群里派单，整改结果不落台账。
- **三个痛点**：
  1. 栏目页有链接但 sitemap 没收录 → 搜索引擎抓不到（漏收）；
  2. 详情页已下线，sitemap 仍指向 404 → 搜索引擎持续抓死链（P0）；
  3. 分页只抓第一页，`rel=next` 缺失时整页漏抓；同一 URL 带 `utm_*` / `#fragment` 被重复计数，重复率报不准。
- **上下游**：三个政务站（栏目页 / sitemap.xml / 详情页）→ 本系统（分页抓取 → URL 规范化 → 三向对账 → 缺陷单）→ 编辑部整改 + 季度考核报表。
- **一天的工作剧本**：
  1. 08:50 主管 `admin` 登录，总览看到上季度覆盖率 96.67%、P0 死链 14 条；
  2. 09:00 在「站点与栏目」核对 `zwgk-hezhou` 的 6 个栏目、120 条目录；
  3. 09:10 用抽屉里的「URL 规范化口径核对」验证 `…/index.html?utm_source=wechat&sessionid=s-01#top` → `…/zcwj/`；
  4. 09:20 巡检专员 `analyst` 在「抓取运行」发起全站巡检（36 个分页清单页）；
  5. 09:22 巡检完成：抓取 393 条链接、canonical 去重 360 条、覆盖率 96.67%；
  6. 09:30 在「对账缺陷」按 P0 筛选，14 条死链逐条看证据链（sitemap loc + HTTP 404）；
  7. 10:00 把 `zcwj-501` 等 3 条标记「已整改」，备注写「已从 sitemap 2026-11 批次移除」；
  8. 10:20 公开办审阅 `viewer` 登录只能看报表，点导出被 403；
  9. 10:30 主管导出 `coverage.csv` / `defects.csv`，行数与页面一致，交季度考核。

## 2. 角色与权限

| 角色 | 账号 | 权限 | 典型动作 |
|---|---|---|---|
| 编辑部主管 `admin` | `admin@sitemapwatch.io` | 登记站点/栏目 + 巡检 + 整改 + 导出 + 审计 | 登记新站、发起巡检、导出报表、看审计 |
| 巡检专员 `analyst` | `analyst@sitemapwatch.io` | 巡检 + 整改 + 导出（不能改站点登记、不能看审计） | 跑巡检、处理缺陷单 |
| 公开办审阅 `viewer` | `viewer@sitemapwatch.io` | 只读（总览 / 站点 / 巡检 / 缺陷明细） | 看覆盖率与缺陷，**不能**巡检、整改、导出、看审计 |

密码统一：`Demo@2026`。低权角色调用高权接口返回 **403**（真实 HTTP 状态，不是前端隐藏）。

## 3. 业务模块表（5-8 个）

| # | 模块名 | 对应页面 | 对应 services + controller | 主要 API |
|---|---|---|---|---|
| ① | 站点与栏目登记 | `#/sites` 站点与栏目 | `site_service` + `catalog_service` + `sitemap_service` / `site_controller` `catalog_controller` | `GET/POST /api/sites`、`PATCH /api/sites/{id}`、`GET/POST /api/catalog`、`GET /api/sitemaps` |
| ② | 分页抓取调度 | `#/crawl-runs` 抓取运行 | `crawl_run_service` + `crawl_engine` / `crawl_run_controller` | `GET/POST /api/crawl-runs`、`GET /api/crawl-runs/{id}` |
| ③ | URL 规范化与采集（算法 A） | `#/sites`（口径核对）+ `#/crawl-runs`（统计） | `services/url_normalize.py` + `services/crawl_engine.py` / `catalog_controller.preview_normalize` | `GET /api/catalog/normalize?url=` |
| ④ | 三向对账（算法 B） | `#/crawl-runs` → `#/defects` | `services/reconcile_engine.py` / `crawl_run_service.execute_run` | `POST /api/crawl-runs` 内触发；`GET /api/defects?run_id=` |
| ⑤ | 缺陷单与整改 | `#/defects` 对账缺陷 | `defect_service` / `defect_controller` | `GET /api/defects`、`GET /api/defects/{id}`、`PATCH /api/defects/{id}/review`、`GET /api/defects/facets` |
| ⑥ | 覆盖率报表与导出 | `#/reports` 报表与导出（含审计页签） | `export_service` + `overview_service` + `audit_service` / `export_controller` | `GET /api/exports/{defects,sites,coverage}.csv`、`GET /api/overview`、`GET /api/audit` |

> 登录（`/api/auth/*`）与审计（`/api/audit`）按约定只算横切能力，不占业务模块配额。

## 4. 快速启动

```bash
cp .env.example .env
docker compose up -d --build
# 等 5/5 healthy
open http://localhost:18201
```

首次启动 backend 会自动建表、写离线 fixture 站并执行一次 seed（`SEED_DEMO=true`）。seed 幂等，可重复执行：

```bash
docker compose exec -T backend python -m scripts.seed_demo
# SEED_SUMMARY brand=sitemapwatch users=3 sources=3 runs=1 findings=31 pending=31
```

## 5. 本地开发

```bash
# backend（测试只需 pytest，不依赖数据库）
cd backend && python -m pip install -r requirements.txt && python -m pytest tests -q
# 前端是静态站点，任意静态服务器即可；接口默认 /api -> 8000
cd frontend/site && python -m http.server 5173
```

## 6. 访问地址

| 服务 | 地址 |
|---|---|
| 前端 | http://localhost:18201 |
| 后端 API 文档 | http://localhost:19201/docs |
| 健康检查 | http://localhost:19201/api/health |
| 数据库映射 | localhost:17701 |

## 7. 技术栈

| 层 | 选型 |
|---|---|
| 前端 | 原生 HTML5 + CSS（oklch 令牌 / Grid + Flex）+ ES Modules；无框架、无打包、无 CDN 脚本 |
| 后端 | Python 3.11、FastAPI 0.115、SQLAlchemy 2.0、PyJWT、passlib(bcrypt) |
| 算法 | 纯 Python 离线实现（`html.parser` 解析 fixture 站 + 集合运算对账），确定性、无外网 |
| 异步 | Celery 5.4 + Redis（worker 心跳、每日 07:40 全站巡检） |
| 数据库 | MySQL 8.0（utf8mb4） |
| 部署 | Docker Compose，恰好 5 服务 |

## 8. 目录

```text
backend/
  src/{config,constants,controllers,middlewares,models,routes,schemas,services,utils}
  scripts/{seed_demo.py,demo_config.py,worker_healthcheck.sh}
  migrations/
  tests/{test_url_normalize.py,test_crawl_engine.py,test_reconcile_engine.py,test_acceptance.py,test_security.py}
frontend/
  site/{index.html,css/{tokens,app}.css,js/{config,api,store,ui,app}.js,js/pages/*.js}
sample_site/<site_code>/         ← seed 运行时在容器内生成（不进仓库）
```

## 9. 环境变量

见 `.env.example`：`COMPOSE_PROJECT_NAME`、`FRONTEND_PORT`、`BACKEND_PORT`、`DB_PORT`、`DB_*`、`JWT_SECRET`、`REDIS_URL`、`SEED_DEMO`、`RATE_LIMIT_*`、`APP_TIMEZONE_OFFSET_MINUTES`。
可选 `SITEMAP_FIXTURE_DIR`（默认 `/app/sample_site`）指定离线 fixture 站根目录。

## 10. 核心算法与口径

### 算法 A｜同站分页抓取 + URL 规范化（`services/url_normalize.py` + `services/crawl_engine.py`）

- **输入**：站点 `home_url` + 磁盘上的离线 fixture 站（真实 HTML 文件；`status.json` 声明 HTTP 状态，`redirects.json` 声明 301）。
- **流程**：首页取栏目 → 逐栏目翻页（`rel=next` 优先；缺失时按 `index_2.html` / `index_3.html` 猜解，猜不到即停）→ 抽取详情链接 → 归一 → 探测可达性（含 301 跟随、`rel=canonical` 读取）。
- **规范化规则**：统一 `https`、主机小写、去默认端口、去 `#fragment`、丢弃 `utm_*` / `sessionid` / `sid` / `from` / `spm`、其余参数按键名排序、`index.html` 折叠成目录尾斜杠、无扩展名补尾斜杠、路径折叠重复斜杠。
- **输出**：`unique_links`（canonical 集合）、`pages[]`（含每页 canonical 去重后的链接数）、`columns[]`、`skipped[]`（`cross_site` / `non_http` / `depth_exceeded` / `fixture_missing`）、`probes{}`、`stats{pages, links, unique, dup_ratio, depth_max, columns}`。重复率 `dup_ratio = 1 - unique/links`。
- **失败态**：首页缺失 → `pages=0` 且 `skipped` 记 `fixture_missing`；301 超过 5 跳 → 状态 508 标记 loop；跨站/非 http 链接不静默丢弃。
- **本批实测**：36 个分页清单页、抓取 393 条链接 → canonical 去重 360 条，重复率 8.40%。

### 算法 B｜三向对账（`services/reconcile_engine.py`）

- **集合定义**：`A` = 目录条目 canonical 集合；`B` = sitemap loc canonical 集合；`C` = 探测返回 200 的集合。
- **分类与严重度**：
  | 判定 | 分类 | 严重度 |
  |---|---|---|
  | `B` 中探测非 200（含 A∩B 但不可达） | `only_in_sitemap_dead` | **P0** |
  | `A - B` | `only_in_catalog` | **P1** |
  | 同一 canonical 被 ≥2 条入口登记 | `duplicate_slug` | **P1** |
  | `A∩B` 且探测有 301 链 | `redirect_chain` | **P2** |
  | `A∩B` 且页面 `rel=canonical` ≠ 自身 | `canonical_mismatch` | **P2** |
- **指标**：覆盖率 `coverage = |A∩B∩C| / |A|`；不可达率 `unreachable_rate = |A\\C| / |A|`；死链率 `sitemap_dead_rate = dead / |B|`。
- **本批实测**：`A=360`、`B=362`、`A∩B∩C=348` → 覆盖率 `348/360 = 96.67%`；缺陷 31 条（P0 14 / P1 12 / P2 5）。

## 11. seed 数量口径

| 项 | 数量 | 说明 |
|---|---|---|
| 账号 | 3 | admin / analyst / viewer，密码 `Demo@2026` |
| 站点（`SEED_SUMMARY sources=`） | 3 | `zwgk-hezhou` / `zwfw-hezhou` / `quxian-hezhou` |
| 目录条目（A） | 360 | 每站 6 栏 × 120 条 |
| 分页清单页 | 36 | 每站 12 页（page_size=12） |
| sitemap loc（B） | 362 | 360 − 12 条漏收 + 14 条死链 |
| 巡检（`runs=`） | 1 | `seed-crawl-2026q4`，触发方式 `seed` |
| 缺陷单（`findings=`） | 31 | P0 14 / P1 12 / P2 5 |
| 待整改（`pending=`） | 31 | seed 不覆盖人工整改状态 |

## 12. 共享枚举出现位置

| 枚举 | 后端 | 前端 |
|---|---|---|
| 角色 `admin/analyst/viewer` | `backend/src/constants/{enums,roles}.py` | `frontend/site/js/config.js`（`ENUMS` 无、`PERMISSIONS`/`ROLE_LABELS`） |
| 缺陷分类 `only_in_catalog/only_in_sitemap_dead/redirect_chain/canonical_mismatch/duplicate_slug` | `backend/src/constants/enums.py::DefectCategory` | `frontend/site/js/config.js::ENUMS.category` |
| 严重度 `p0/p1/p2` | `backend/src/constants/enums.py::DefectSeverity` + `CATEGORY_SEVERITY` | `ENUMS.severity` |
| 整改状态 `pending/fixed/ignored` | `backend/src/constants/enums.py::DefectStatus` | `ENUMS.defectStatus` |
| 巡检状态 `queued/running/success/partial/failed` | `backend/src/constants/enums.py::CrawlStatus` | `ENUMS.crawlStatus` |
| 触发方式 `manual/schedule/seed` | `backend/src/constants/enums.py::TriggerKind` | `ENUMS.trigger` |
| 分页发现方式 `home_link/rel_next/index_guess/sitemap_probe` | `backend/src/constants/enums.py::DiscoverySource` | `ENUMS.discovery` |

## 13. 视觉方向

档案馆索引卡：**靛蓝 `oklch(0.443 0.132 268)` + 卡片米 `oklch(0.951 0.019 88)` + 钢笔墨 `oklch(0.268 0.044 264)`**；双字体 `Cormorant Garamond`（档案正题）+ `Noto Sans SC`（正文），索引卡标签用 `Courier Prime` 打字机。
登录页做成「卷宗检索」：左侧一叠索引卡（档号 / 卷宗 / 保管期限 / 办理方式），右侧「借阅登记卡」表单带骑缝线；总览页把覆盖率做成仪表 + P0/P1/P2 分诊条 + 三张站点索引卡。令牌全部在 `frontend/site/css/tokens.css`，无纯黑白、无紫蓝渐变、无玻璃拟态。

## 14. Docker 说明

- 5 个服务：`frontend`(Nginx 静态站) / `backend`(uvicorn) / `worker`(Celery) / `db`(MySQL 8.0) / `redis`，全部带 healthcheck。
- 命名卷：`db_data`、`redis_data`。
- Nginx：`location /api/ { proxy_pass http://backend:8000/; }` + SPA 回落。
- 收尾：`docker compose down -v --remove-orphans`。

## License

内部演示项目，仅用于评测与教学。
