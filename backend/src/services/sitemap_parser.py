"""sitemap XML 解析：sitemap index + 多份子清单（urlset）。

政务站把 sitemap 拆成多份后，磁盘/线上的形态是：

    sitemap.xml            -> <sitemapindex>，声明若干子清单
    sitemap-news.xml       -> <urlset>，真正的 <url><loc> 条目
    sitemap-xxgk.xml       -> <urlset>
    ...

解析器只依赖标准库，产出结构化 dict；网络/磁盘读取由调用方负责，
失败（超时、404、XML 解析错误）由调用方包成 ``SourceInput(ok=False)``，
裁决器据此沿用上一版而不是当成"空清单"。
"""
from __future__ import annotations

import xml.etree.ElementTree as ET
from html import unescape

SITEMAP_NS = "http://www.sitemaps.org/schemas/sitemap/0.9"
_NS = f"{{{SITEMAP_NS}}}"


class SitemapParseError(ValueError):
    """sitemap XML 无法解析或根节点不是 sitemapindex/urlset。"""


def _local_name(tag: str) -> str:
    return tag.split("}", 1)[1] if "}" in tag else tag


def _text(element: ET.Element, name: str) -> str | None:
    node = element.find(f"{_NS}{name}")
    if node is None:
        # 兼容不带命名空间的 sitemap
        node = next((child for child in element if _local_name(child.tag) == name), None)
    if node is None or node.text is None:
        return None
    value = unescape(node.text.strip())
    return value or None


def parse_sitemap(xml_text: str) -> dict:
    """解析一段 sitemap XML。

    返回 ``{"kind": "index"|"urlset", ...}``：
    - index: ``{"kind": "index", "children": [{"loc", "lastmod"}, ...]}``
    - urlset: ``{"kind": "urlset", "urls": [{"loc", "lastmod", "changefreq", "priority"}, ...]}``
    """
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        raise SitemapParseError(f"XML 解析失败：{exc}") from exc
    kind = _local_name(root.tag)
    if kind == "sitemapindex":
        children = []
        for node in root:
            if _local_name(node.tag) != "sitemap":
                continue
            loc = _text(node, "loc")
            if loc:
                children.append({"loc": loc, "lastmod": _text(node, "lastmod")})
        return {"kind": "index", "children": children}
    if kind == "urlset":
        urls = []
        for node in root:
            if _local_name(node.tag) != "url":
                continue
            loc = _text(node, "loc")
            if not loc:
                continue
            priority_raw = _text(node, "priority")
            try:
                priority = float(priority_raw) if priority_raw is not None else 0.8
            except ValueError:
                priority = 0.8
            urls.append(
                {
                    "loc": loc,
                    "lastmod": _text(node, "lastmod"),
                    "changefreq": _text(node, "changefreq") or "weekly",
                    "priority": min(1.0, max(0.0, priority)),
                }
            )
        return {"kind": "urlset", "urls": urls}
    raise SitemapParseError(f"未知根节点 <{kind}>，应为 sitemapindex 或 urlset")


def source_filename(url_or_path: str) -> str:
    """从子清单 URL/路径取文件名，作为 source_file 自然键。"""
    tail = str(url_or_path).rstrip("/").rsplit("/", 1)[-1]
    return tail or "sitemap.xml"
