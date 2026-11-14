"""sitemap index / urlset 解析单测。"""
from __future__ import annotations

import pytest

from src.services.sitemap_parser import SitemapParseError, parse_sitemap, source_filename

INDEX = """<?xml version="1.0" encoding="UTF-8"?>
<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <sitemap><loc>https://zwgk.hezhou.gov.cn/sitemap-zcwj.xml</loc><lastmod>2026-10-08</lastmod></sitemap>
  <sitemap><loc>https://zwgk.hezhou.gov.cn/sitemap-czjs.xml</loc></sitemap>
</sitemapindex>
"""

URLSET = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url>
    <loc>https://zwgk.hezhou.gov.cn/xxgk/zcwj/zcwj-001.html</loc>
    <lastmod>2026-10-01</lastmod>
    <changefreq>weekly</changefreq>
    <priority>0.8</priority>
  </url>
  <url>
    <loc>https://zwgk.hezhou.gov.cn/xxgk/zcwj/zcwj-002.html</loc>
    <lastmod>2026-09-01</lastmod>
  </url>
</urlset>
"""


def test_parse_sitemap_index():
    parsed = parse_sitemap(INDEX)
    assert parsed["kind"] == "index"
    assert [child["loc"].rsplit("/", 1)[-1] for child in parsed["children"]] == [
        "sitemap-zcwj.xml",
        "sitemap-czjs.xml",
    ]
    assert parsed["children"][0]["lastmod"] == "2026-10-08"
    assert parsed["children"][1]["lastmod"] is None


def test_parse_urlset_with_defaults():
    parsed = parse_sitemap(URLSET)
    assert parsed["kind"] == "urlset"
    assert len(parsed["urls"]) == 2
    first, second = parsed["urls"]
    assert first["lastmod"] == "2026-10-01"
    assert first["priority"] == 0.8
    # 缺省 changefreq/priority 给默认值
    assert second["changefreq"] == "weekly"
    assert second["priority"] == 0.8


def test_parse_rejects_broken_xml():
    with pytest.raises(SitemapParseError):
        parse_sitemap("<urlset><url><loc>oops")


def test_parse_rejects_unknown_root():
    with pytest.raises(SitemapParseError):
        parse_sitemap('<?xml version="1.0"?><html></html>')


def test_source_filename():
    assert source_filename("https://x.gov.cn/a/sitemap-zcwj.xml") == "sitemap-zcwj.xml"
    assert source_filename("/sitemap.xml") == "sitemap.xml"
