# 数据库迁移说明

本项目用 SQLAlchemy `Base.metadata.create_all()` 在 backend 启动时建表（见 `src/config/app.py`），
因此首次 `docker compose up` 会自动建好表，不需要额外执行迁移。

- `001_core_tables.sql`：核心表的人类可读 DDL 参考（MySQL 8.0 语法），用于 reviewer 对照字段；
  运行时不执行它。
- 多子清单版本化新增表 `sitemap_sources` / `sitemap_versions` / `sitemap_rounds` /
  `crawl_run_sitemaps`，以及 `sitemap_entries` 的唯一键由 `(site_id, loc)` 改为
  `(site_id, canonical_url)` 并增加 `is_gap`，DDL 已同步在 `001_core_tables.sql`；
  新环境由 `create_all()` 直接建出，旧环境升级需先按该 DDL 手工补表/改键。
- 后续如果要做字段变更，建议引入 Alembic，并在本目录按 `00x_<描述>.py` 递增。
- seed 数据只走 `backend/scripts/seed_demo.py`，不要写进 SQL。
