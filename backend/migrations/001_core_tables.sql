-- 核心表结构参考（MySQL 8.0 语法，运行时不执行；建表由 SQLAlchemy create_all 完成）

CREATE TABLE users (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    email           VARCHAR(160) NOT NULL UNIQUE,
    password_hash   VARCHAR(255) NOT NULL,
    display_name    VARCHAR(80)  NOT NULL,
    role            VARCHAR(20)  NOT NULL,
    org             VARCHAR(120),
    created_at      DATETIME     NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE sites (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    code            VARCHAR(40)  NOT NULL UNIQUE,
    name            VARCHAR(120) NOT NULL,
    home_url        VARCHAR(200) NOT NULL,
    sitemap_url     VARCHAR(200),
    dept            VARCHAR(120),
    region          VARCHAR(40),
    page_size       INT NOT NULL DEFAULT 12,
    max_depth       INT NOT NULL DEFAULT 3,
    note            TEXT,
    config          JSON,
    enabled         TINYINT(1) NOT NULL DEFAULT 1,
    last_crawled_at DATETIME,
    created_at      DATETIME NOT NULL,
    updated_at      DATETIME NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE catalog_items (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    site_id         INT NOT NULL,
    column_code     VARCHAR(60)  NOT NULL,
    column_name     VARCHAR(120),
    entry_url       VARCHAR(300) NOT NULL,
    canonical_url   VARCHAR(300) NOT NULL,
    page_no         INT NOT NULL DEFAULT 1,
    item_no         INT NOT NULL DEFAULT 0,
    depth           INT NOT NULL DEFAULT 2,
    discovered_from VARCHAR(20),
    title           VARCHAR(200),
    enabled         TINYINT(1) NOT NULL DEFAULT 1,
    created_at      DATETIME NOT NULL,
    CONSTRAINT uq_catalog_site_entry UNIQUE (site_id, entry_url),
    CONSTRAINT fk_catalog_site FOREIGN KEY (site_id) REFERENCES sites(id) ON DELETE CASCADE,
    INDEX ix_catalog_canonical (canonical_url)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE sitemap_entries (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    site_id         INT NOT NULL,
    loc             VARCHAR(300) NOT NULL,
    canonical_url   VARCHAR(300) NOT NULL,
    lastmod         VARCHAR(20),
    changefreq      VARCHAR(20),
    priority        DOUBLE NOT NULL DEFAULT 0.8,
    source_file     VARCHAR(120),
    is_gap          TINYINT(1) NOT NULL DEFAULT 0,
    created_at      DATETIME NOT NULL,
    updated_at      DATETIME NOT NULL,
    CONSTRAINT uq_sitemap_site_canonical UNIQUE (site_id, canonical_url),
    CONSTRAINT fk_sitemap_site FOREIGN KEY (site_id) REFERENCES sites(id) ON DELETE CASCADE,
    INDEX ix_sitemap_canonical (canonical_url),
    INDEX ix_sitemap_source (site_id, source_file),
    INDEX ix_sitemap_gap (is_gap)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 子清单登记：一个站点的一份 sitemap 分片
CREATE TABLE sitemap_sources (
    id                  INT AUTO_INCREMENT PRIMARY KEY,
    site_id             INT NOT NULL,
    source_file         VARCHAR(200) NOT NULL,
    source_url          VARCHAR(300),
    status              VARCHAR(20) NOT NULL DEFAULT 'ok',
    last_error          TEXT,
    last_success_hash   VARCHAR(64),
    last_success_at     DATETIME,
    last_attempt_at     DATETIME,
    created_at          DATETIME NOT NULL,
    updated_at          DATETIME NOT NULL,
    CONSTRAINT uq_source_site_file UNIQUE (site_id, source_file),
    CONSTRAINT fk_source_site FOREIGN KEY (site_id) REFERENCES sites(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 子清单版本：每次到达（成功/失败）一条不可变留痕
CREATE TABLE sitemap_versions (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    source_id       INT NOT NULL,
    site_id         INT NOT NULL,
    round_id        INT NULL,
    status          VARCHAR(20) NOT NULL,
    content_hash    VARCHAR(64),
    entry_count     INT NOT NULL DEFAULT 0,
    payload         JSON,
    error           TEXT,
    created_at      DATETIME NOT NULL,
    CONSTRAINT fk_version_source FOREIGN KEY (source_id) REFERENCES sitemap_sources(id) ON DELETE CASCADE,
    CONSTRAINT fk_version_site FOREIGN KEY (site_id) REFERENCES sites(id) ON DELETE CASCADE,
    INDEX ix_version_source (source_id),
    INDEX ix_version_round (round_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 同步轮次：一次多子清单拉取 + lastmod 裁决的留痕
CREATE TABLE sitemap_rounds (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    site_id         INT NOT NULL,
    round_no        VARCHAR(40) NOT NULL,
    status          VARCHAR(20) NOT NULL DEFAULT 'success',
    source_total    INT NOT NULL DEFAULT 0,
    source_failed   INT NOT NULL DEFAULT 0,
    entry_total     INT NOT NULL DEFAULT 0,
    gap_count       INT NOT NULL DEFAULT 0,
    source_hashes   JSON,
    stats           JSON,
    note            TEXT,
    triggered_by    VARCHAR(160) NOT NULL DEFAULT 'system',
    created_at      DATETIME NOT NULL,
    CONSTRAINT fk_round_site FOREIGN KEY (site_id) REFERENCES sites(id) ON DELETE CASCADE,
    INDEX ix_round_site (site_id, id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE crawl_runs (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    run_no          VARCHAR(40) NOT NULL UNIQUE,
    site_id         INT NULL,
    `trigger`       VARCHAR(20) NOT NULL,
    status          VARCHAR(20) NOT NULL,
    operator_email  VARCHAR(160) NOT NULL,
    pages           INT NOT NULL DEFAULT 0,
    links           INT NOT NULL DEFAULT 0,
    unique_links    INT NOT NULL DEFAULT 0,
    dup_ratio       DOUBLE NOT NULL DEFAULT 0,
    depth_max       INT NOT NULL DEFAULT 0,
    sitemap_count   INT NOT NULL DEFAULT 0,
    catalog_count   INT NOT NULL DEFAULT 0,
    coverage        DOUBLE NOT NULL DEFAULT 0,
    unreachable_rate DOUBLE NOT NULL DEFAULT 0,
    defect_count    INT NOT NULL DEFAULT 0,
    p0_count        INT NOT NULL DEFAULT 0,
    p1_count        INT NOT NULL DEFAULT 0,
    p2_count        INT NOT NULL DEFAULT 0,
    metrics         JSON,
    log_text        TEXT,
    seed_key        VARCHAR(120) UNIQUE,
    sitemap_round_ids JSON,
    affected_sites  JSON,
    started_at      DATETIME NOT NULL,
    finished_at     DATETIME,
    CONSTRAINT fk_run_site FOREIGN KEY (site_id) REFERENCES sites(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 巡检轮次冻结的 sitemap 口径快照：对账/覆盖率/导出都读它
CREATE TABLE crawl_run_sitemaps (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    run_id          INT NOT NULL,
    site_id         INT NOT NULL,
    loc             VARCHAR(300) NOT NULL,
    canonical_url   VARCHAR(300) NOT NULL,
    lastmod         VARCHAR(20),
    changefreq      VARCHAR(20),
    priority        DOUBLE NOT NULL DEFAULT 0.8,
    source_file     VARCHAR(120) NOT NULL DEFAULT 'sitemap.xml',
    is_gap          TINYINT(1) NOT NULL DEFAULT 0,
    CONSTRAINT uq_run_sitemap_canonical UNIQUE (run_id, canonical_url),
    CONSTRAINT fk_runsnap_run FOREIGN KEY (run_id) REFERENCES crawl_runs(id) ON DELETE CASCADE,
    CONSTRAINT fk_runsnap_site FOREIGN KEY (site_id) REFERENCES sites(id) ON DELETE CASCADE,
    INDEX ix_runsnap_run (run_id),
    INDEX ix_runsnap_site (site_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE defects (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    run_id          INT NOT NULL,
    site_id         INT NULL,
    site_code       VARCHAR(40),
    category        VARCHAR(40) NOT NULL,
    severity        VARCHAR(8)  NOT NULL,
    fingerprint     VARCHAR(160) NOT NULL,
    url             VARCHAR(300) NOT NULL,
    canonical_url   VARCHAR(300),
    column_name     VARCHAR(120),
    title           VARCHAR(200) NOT NULL,
    summary         TEXT,
    status          VARCHAR(16) NOT NULL DEFAULT 'pending',
    evidence        JSON,
    reviewer        VARCHAR(160),
    review_note     TEXT,
    created_at      DATETIME NOT NULL,
    updated_at      DATETIME NOT NULL,
    CONSTRAINT uq_defects_run_fp UNIQUE (run_id, fingerprint),
    CONSTRAINT fk_defect_run FOREIGN KEY (run_id) REFERENCES crawl_runs(id) ON DELETE CASCADE,
    CONSTRAINT fk_defect_site FOREIGN KEY (site_id) REFERENCES sites(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE audit_logs (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    actor_email     VARCHAR(160) NOT NULL,
    actor_role      VARCHAR(20)  NOT NULL,
    action          VARCHAR(64)  NOT NULL,
    entity          VARCHAR(40)  NOT NULL,
    entity_id       VARCHAR(64),
    detail          JSON,
    layer           VARCHAR(16) NOT NULL DEFAULT 'domain',
    ip              VARCHAR(64),
    seed_key        VARCHAR(120) UNIQUE,
    created_at      DATETIME NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
