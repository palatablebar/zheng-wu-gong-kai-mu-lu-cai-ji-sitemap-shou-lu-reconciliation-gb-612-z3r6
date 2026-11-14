"""算法 A｜同站分页抓取 + URL 规范化（离线 fixture 站，确定性）。

输入：站点首页 + 磁盘上的静态 HTML fixture（`sample_site/<site_code>/…`）
      · `status.json`    —— fixture 侧声明的 HTTP 状态（默认：文件存在 200、不存在 404）
      · `redirects.json` —— fixture 侧声明的 301 跳转（path -> 目标 path）
输出：分页清单、详情链接集合（canonical）、可达性探测结果、抓取统计。

处理的关键点（对应 batch-plan 算法 A）：
- `rel=next` 优先；缺失时按 `index_2.html` / `index_3.html` 猜解，猜不到即停；
- 去 `utm_*` / `sessionid` / `#fragment`，统一 https + 尾斜杠（见 url_normalize）；
- 跟随 301 并记录 redirect chain；
- 跨站链接、非 http 协议、深度超限、fixture 缺失 → 进 `skipped`，不静默丢弃。
"""
from __future__ import annotations

import json
import re
from html.parser import HTMLParser
from pathlib import Path

from src.services.url_normalize import normalize_url, same_site, url_path

PAGINATION_RE = re.compile(r"/index(_\d+)?\.html?$", re.IGNORECASE)
DETAIL_RE = re.compile(r"\.html?$", re.IGNORECASE)
MAX_PROBE_HOPS = 5
REDIRECT_STATUSES = (301, 302, 307, 308)


class _PageParser(HTMLParser):
    """极简 HTML 解析：锚点、rel=next、rel=canonical、title。"""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.links: list[tuple[str, str]] = []
        self.next_href: str | None = None
        self.canonical: str | None = None
        self.title = ""
        self._anchor_href: str | None = None
        self._anchor_text: list[str] = []
        self._in_title = False

    def handle_starttag(self, tag: str, attrs) -> None:  # noqa: D102
        values = {key: (value or "") for key, value in attrs}
        if tag == "a" and values.get("href"):
            self._anchor_href = values["href"]
            self._anchor_text = []
        elif tag == "link":
            rels = values.get("rel", "").lower().split()
            href = values.get("href")
            if href and "next" in rels:
                self.next_href = href
            if href and "canonical" in rels:
                self.canonical = href
        elif tag == "title":
            self._in_title = True

    def handle_endtag(self, tag: str) -> None:  # noqa: D102
        if tag == "a" and self._anchor_href is not None:
            self.links.append((self._anchor_href, "".join(self._anchor_text).strip()))
            self._anchor_href = None
            self._anchor_text = []
        elif tag == "title":
            self._in_title = False

    def handle_data(self, data: str) -> None:  # noqa: D102
        if self._anchor_href is not None:
            self._anchor_text.append(data)
        if self._in_title:
            self.title += data


def parse_page(html: str) -> _PageParser:
    parser = _PageParser()
    parser.feed(html)
    parser.close()
    parser.title = " ".join(parser.title.split())
    return parser


def extract_canonical(html: str | None) -> str | None:
    if not html:
        return None
    return parse_page(html).canonical


def _load_map(root: Path, name: str) -> dict:
    path = root / name
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    return data if isinstance(data, dict) else {}


def file_path_for(url: str) -> str:
    """canonical URL -> fixture 相对路径（目录 URL 取 index.html）。"""
    path = url_path(url)
    if path.endswith("/"):
        return f"{path}index.html"
    return path


def read_fixture(root: Path, url: str) -> str | None:
    target = root / file_path_for(url).lstrip("/")
    try:
        if target.is_file():
            return target.read_text(encoding="utf-8")
    except OSError:
        return None
    return None


class SiteFixture:
    """一个站点的离线 fixture 访问层（HTTP 语义的本地替身）。"""

    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self.status_map: dict[str, int] = {
            str(key): int(value) for key, value in _load_map(self.root, "status.json").items()
        }
        self.redirect_map: dict[str, str] = {
            str(key): str(value) for key, value in _load_map(self.root, "redirects.json").items()
        }

    def html(self, url: str) -> str | None:
        return read_fixture(self.root, url)

    def probe(self, url: str) -> dict:
        """GET 一条 URL：解析 301 链、最终状态、页面 canonical。"""
        chain: list[dict] = []
        current = normalize_url(url)
        seen: set[str] = set()
        for _ in range(MAX_PROBE_HOPS):
            if current in seen:
                return {
                    "requested": normalize_url(url),
                    "final_url": current,
                    "status": 508,
                    "redirect_chain": chain,
                    "canonical_tag": None,
                    "loop": True,
                }
            seen.add(current)
            path = file_path_for(current)
            html = self.html(current)
            if path in self.redirect_map:
                status = 301
            elif path in self.status_map:
                status = int(self.status_map[path])
            else:
                status = 200 if html is not None else 404
            if status in REDIRECT_STATUSES:
                target = self.redirect_map.get(path)
                if not target:
                    return {
                        "requested": normalize_url(url),
                        "final_url": current,
                        "status": status,
                        "redirect_chain": chain,
                        "canonical_tag": None,
                        "loop": False,
                    }
                following = normalize_url(target, base=current)
                chain.append({"from": current, "to": following, "status": status})
                current = following
                continue
            return {
                "requested": normalize_url(url),
                "final_url": current,
                "status": status,
                "redirect_chain": chain,
                "canonical_tag": extract_canonical(html) if status == 200 else None,
                "loop": False,
            }
        return {
            "requested": normalize_url(url),
            "final_url": current,
            "status": 508,
            "redirect_chain": chain,
            "canonical_tag": None,
            "loop": True,
        }


def _column_entry(url: str, home_url: str) -> bool:
    if not same_site(url, home_url):
        return False
    path = url_path(url)
    return path.startswith("/") and path.count("/") >= 2 and path.endswith("/")


def _guess_next(page_url: str, fixture: SiteFixture, page_no: int) -> str | None:
    candidate = normalize_url(f"index_{page_no + 1}.html", base=page_url)
    if fixture.html(candidate) is not None:
        return candidate
    return None


def crawl_site(
    *,
    home_url: str,
    fixture_root: Path,
    page_size: int = 12,
    max_depth: int = 3,
    max_pages: int = 80,
) -> dict:
    """分页抓取一个站点，返回 canonical 集合与统计（确定性：两次调用结果完全一致）。"""
    fixture = SiteFixture(fixture_root)
    home = normalize_url(home_url)
    pages: list[dict] = []
    columns: list[dict] = []
    links: list[dict] = []
    skipped: list[dict] = []
    seen_pages: set[str] = set()
    seen_link_canonical: dict[str, dict] = {}

    home_html = fixture.html(home)
    if home_html is None:
        return {
            "site_home": home,
            "pages": [],
            "columns": [],
            "links": [],
            "unique_links": [],
            "skipped": [{"url": home, "reason": "fixture_missing"}],
            "probes": {},
            "stats": {"pages": 0, "links": 0, "unique": 0, "dup_ratio": 0.0, "depth_max": 0, "columns": 0},
        }

    home_parsed = parse_page(home_html)
    skipped.append({"url": f"{home}robots.txt", "reason": "non_listing"})
    for href, text in home_parsed.links:
        if href.lower().startswith(("mailto:", "javascript:", "tel:")):
            skipped.append({"url": href, "reason": "non_http"})
            continue
        absolute = normalize_url(href, base=home)
        if not same_site(absolute, home):
            skipped.append({"url": absolute, "reason": "cross_site"})
            continue
        if not _column_entry(absolute, home):
            continue
        columns.append({"url": absolute, "name": text or absolute})

    for column in columns:
        entry = column["url"]
        parsed_entry = parse_page(fixture.html(entry) or "")
        column["name"] = column["name"] or parsed_entry.title
        column["pages"] = 0
        current = entry
        page_no = 1
        discovered_from = "home_link"
        while current and len(pages) < max_pages:
            if current in seen_pages:
                break
            seen_pages.add(current)
            html = fixture.html(current)
            if html is None:
                skipped.append({"url": current, "reason": "fixture_missing"})
                break
            parsed = parse_page(html)
            page = {
                "url": current,
                "title": parsed.title,
                "column_url": entry,
                "column_name": column["name"],
                "page_no": page_no,
                "discovered_from": discovered_from,
                "links_in_page": 0,
            }
            page_canonicals: set[str] = set()
            for href, text in parsed.links:
                if href.lower().startswith(("mailto:", "javascript:", "tel:")):
                    skipped.append({"url": href, "reason": "non_http"})
                    continue
                absolute = normalize_url(href, base=current)
                if not same_site(absolute, home):
                    skipped.append({"url": absolute, "reason": "cross_site"})
                    continue
                if PAGINATION_RE.search(url_path(absolute)):
                    continue
                if not DETAIL_RE.search(url_path(absolute)):
                    continue
                if max_depth < 2:
                    skipped.append({"url": absolute, "reason": "depth_exceeded"})
                    continue
                page_canonicals.add(absolute)
                links.append(
                    {
                        "raw": href,
                        "canonical": absolute,
                        "column_url": entry,
                        "column_name": column["name"],
                        "page_no": page_no,
                        "page_url": current,
                        "depth": 2,
                        "discovered_from": discovered_from,
                        "title": text,
                    }
                )
                if absolute not in seen_link_canonical:
                    seen_link_canonical[absolute] = links[-1]
            page["links_in_page"] = len(page_canonicals)
            pages.append(page)
            column["pages"] += 1
            next_url = None
            if parsed.next_href:
                candidate = normalize_url(parsed.next_href, base=current)
                if same_site(candidate, home) and fixture.html(candidate) is not None:
                    next_url = candidate
                    discovered_from = "rel_next"
            if next_url is None:
                guess = _guess_next(current, fixture, page_no)
                if guess is not None:
                    next_url = guess
                    discovered_from = "index_guess"
            current = next_url
            page_no += 1

    columns = [column for column in columns if column.get("pages", 0) > 0]
    unique_links = sorted(seen_link_canonical)
    probes = {canonical: fixture.probe(canonical) for canonical in unique_links}
    total_links = len(links)
    unique_count = len(unique_links)
    dup_ratio = round(1 - (unique_count / total_links), 4) if total_links else 0.0
    depth_max = max((link["depth"] for link in links), default=0)

    return {
        "site_home": home,
        "pages": pages,
        "columns": columns,
        "links": sorted(links, key=lambda item: (item["canonical"], item["raw"])),
        "unique_links": unique_links,
        "skipped": skipped,
        "probes": probes,
        "stats": {
            "pages": len(pages),
            "links": total_links,
            "unique": unique_count,
            "dup_ratio": dup_ratio,
            "depth_max": depth_max,
            "columns": len(columns),
            "page_size": page_size,
        },
    }


def probe_urls(fixture_root: Path, urls: list[str]) -> dict[str, dict]:
    """对 sitemap 里的 loc 做可达性探测（三向对账需要 C 集合之外的 B 侧状态）。"""
    fixture = SiteFixture(fixture_root)
    return {normalize_url(url): fixture.probe(url) for url in sorted(urls)}
