"""算法 A｜同站分页抓取单测：rel=next、页码猜解、去重、跨站/深度跳过、301 链、确定性。"""
from __future__ import annotations

import json
from pathlib import Path

from src.services import crawl_engine

HOME = "https://mini.gov.cn"

MINI_FILES = {
    "/index.html": """<!doctype html><html><head><title>迷你政务站</title></head><body>
  <a href="https://mini.gov.cn/xxgk/col1/index.html">栏目一</a>
  <a href="https://other.gov.cn/xxgk/x/index.html">外部站</a>
  <a href="mailto:zwgk@mini.gov.cn">邮箱</a>
  <a href="/xxgk/ghost/">缺 fixture 栏目</a>
</body></html>""",
    "/xxgk/col1/index.html": """<!doctype html><html><head><title>栏目一 第 1 页</title>
  <link rel="canonical" href="https://mini.gov.cn/xxgk/col1/" />
  <link rel="next" href="index_2.html" />
</head><body>
  <a href="col1-001.html">文件一</a>
  <a href="col1-001.html?utm_source=wx&amp;sessionid=s-1#top">文件一镜像</a>
  <a href="col1-002.html">文件二</a>
</body></html>""",
    "/xxgk/col1/index_2.html": """<!doctype html><html><head><title>栏目一 第 2 页</title>
  <link rel="canonical" href="https://mini.gov.cn/xxgk/col1/index_2.html" />
</head><body>
  <a href="col1-003.html">文件三</a>
  <a href="col1-004.html">文件四</a>
</body></html>""",
    "/xxgk/col1/index_3.html": """<!doctype html><html><head><title>栏目一 第 3 页</title></head><body>
  <a href="col1-005.html">文件五</a>
</body></html>""",
}

DETAIL_CANONICAL = {
    "col1-001.html": "self",
    "col1-002.html": "self",
    "col1-003.html": "self",
    "col1-004.html": "self",
    "col1-005.html": "self",
}

REDIRECTS = {"/xxgk/col1/col1-004.html": "/xxgk/col1/col1-005.html"}


def _write(root: Path, relative: str, text: str) -> None:
    target = root / relative.lstrip("/")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")


def build_mini(root: Path, *, redirects: dict[str, str] | None = None) -> Path:
    for relative, text in MINI_FILES.items():
        _write(root, relative, text)
    for name, mode in DETAIL_CANONICAL.items():
        canonical = f"{HOME}/xxgk/col1/{name}" if mode == "self" else mode
        _write(
            root,
            f"/xxgk/col1/{name}",
            f"""<!doctype html><html><head><title>{name}</title>
  <link rel="canonical" href="{canonical}" />
</head><body><article>{name}</article></body></html>""",
        )
    _write(root, "/redirects.json", json.dumps(redirects or {}, ensure_ascii=False))
    _write(root, "/status.json", json.dumps({"__none__": 200}, ensure_ascii=False))
    return root


def crawl(root: Path, **kwargs) -> dict:
    return crawl_engine.crawl_site(home_url=HOME, fixture_root=root, **kwargs)


def test_rel_next_and_index_guess_pagination(tmp_path):
    root = build_mini(tmp_path)
    result = crawl(root)
    page_urls = [page["url"] for page in result["pages"]]
    assert page_urls == [
        "https://mini.gov.cn/xxgk/col1/",
        "https://mini.gov.cn/xxgk/col1/index_2.html",
        "https://mini.gov.cn/xxgk/col1/index_3.html",
    ]
    sources = [page["discovered_from"] for page in result["pages"]]
    assert sources == ["home_link", "rel_next", "index_guess"]
    assert result["stats"]["pages"] == 3


def test_dedup_and_dup_ratio(tmp_path):
    root = build_mini(tmp_path)
    result = crawl(root)
    # 6 个锚点（含 utm 变体与 #fragment 重复）→ 5 条 canonical
    assert result["stats"]["links"] == 6
    assert result["stats"]["unique"] == 5
    assert result["stats"]["dup_ratio"] == 0.1667
    assert "https://mini.gov.cn/xxgk/col1/col1-001.html" in result["unique_links"]


def test_skips_cross_site_non_http_and_missing(tmp_path):
    root = build_mini(tmp_path)
    result = crawl(root)
    reasons = {item["reason"] for item in result["skipped"]}
    assert {"cross_site", "non_http", "fixture_missing"} <= reasons
    assert result["stats"]["columns"] == 1


def test_depth_limit_blocks_detail_links(tmp_path):
    root = build_mini(tmp_path)
    result = crawl(root, max_depth=1)
    assert result["stats"]["links"] == 0
    assert any(item["reason"] == "depth_exceeded" for item in result["skipped"])


def test_follows_301_chain(tmp_path):
    root = build_mini(tmp_path, redirects=REDIRECTS)
    (root / "xxgk/col1/col1-004.html").unlink()
    result = crawl(root)
    probe = result["probes"]["https://mini.gov.cn/xxgk/col1/col1-004.html"]
    assert probe["status"] == 200
    assert probe["final_url"] == "https://mini.gov.cn/xxgk/col1/col1-005.html"
    assert len(probe["redirect_chain"]) == 1
    assert probe["redirect_chain"][0]["from"] == "https://mini.gov.cn/xxgk/col1/col1-004.html"


def test_deterministic(tmp_path):
    root = build_mini(tmp_path)
    first = crawl(root)
    second = crawl(root)
    assert first == second
    assert first["unique_links"] == sorted(first["unique_links"])


def test_status_json_marks_dead(tmp_path):
    root = build_mini(tmp_path)
    _write(root, "/status.json", json.dumps({"/xxgk/col1/col1-002.html": 404}, ensure_ascii=False))
    result = crawl(root)
    assert result["probes"]["https://mini.gov.cn/xxgk/col1/col1-002.html"]["status"] == 404
