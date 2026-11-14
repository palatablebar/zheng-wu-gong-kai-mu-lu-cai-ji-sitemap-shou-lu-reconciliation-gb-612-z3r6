"""URL 规范化（算法 A 的第一段，纯函数、确定性）。

规则（README「URL 规范化口径」一节同步说明）：
1. 相对路径按所在页面解析成绝对 URL；
2. 协议统一为 https，主机小写，去掉默认端口；
3. 去掉 `#fragment`；
4. 丢弃追踪参数 `utm_*` / `sessionid` / `sid` / `from` / `spm`；
5. 其余查询参数按键名排序后重新拼接（空查询不保留 `?`）；
6. 路径折叠重复斜杠；`index.html` 结尾折叠成目录形式并补尾斜杠；
7. 无扩展名的路径补尾斜杠（目录页口径）。
"""
from __future__ import annotations

from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit

TRACKING_PARAMS: frozenset[str] = frozenset(
    {
        "utm_source",
        "utm_medium",
        "utm_campaign",
        "utm_term",
        "utm_content",
        "utm_id",
        "sessionid",
        "sid",
        "from",
        "spm",
    }
)

DIRECTORY_INDEXES = ("index.html", "index.htm", "default.html")


def is_tracking_param(name: str) -> bool:
    lowered = name.lower()
    if lowered in TRACKING_PARAMS:
        return True
    return lowered.startswith("utm_")


def _fold_slashes(path: str) -> str:
    while "//" in path:
        path = path.replace("//", "/")
    return path or "/"


def _fold_index(path: str) -> str:
    segment = path.rsplit("/", 1)[-1].lower()
    if segment in DIRECTORY_INDEXES:
        path = path[: -len(segment)]
        if not path.endswith("/"):
            path += "/"
    return path


def _maybe_trailing_slash(path: str) -> str:
    if path.endswith("/"):
        return path
    last = path.rsplit("/", 1)[-1]
    if last and "." not in last:
        return path + "/"
    return path


def normalize_url(raw: str | None, base: str | None = None) -> str:
    """把任意写法归一成唯一 canonical 字符串。无法解析时返回去空白的原值。"""
    if raw is None:
        return ""
    text = str(raw).strip()
    if not text:
        return ""
    if text.startswith("#"):
        return normalize_url(base) if base else ""
    absolute = urljoin(base, text) if base else text
    parts = urlsplit(absolute)
    if not parts.scheme or not parts.netloc:
        return text
    host = (parts.hostname or "").lower()
    port = parts.port
    netloc = host if (not port or port in (80, 443)) else f"{host}:{port}"
    query_pairs = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True) if not is_tracking_param(k)]
    query = urlencode(sorted(query_pairs), doseq=True)
    path = _maybe_trailing_slash(_fold_index(_fold_slashes(parts.path or "/")))
    return urlunsplit(("https", netloc, path, query, ""))


def url_path(url: str) -> str:
    """取规范化 URL 的路径部分，用于离线 fixture 的磁盘映射。"""
    return urlsplit(url).path or "/"


def url_host(url: str) -> str:
    return (urlsplit(url).hostname or "").lower()


def same_site(url: str, home_url: str) -> bool:
    host = url_host(url)
    home = url_host(home_url)
    if not host or not home:
        return False
    if host == home:
        return True
    return host.removeprefix("www.") == home.removeprefix("www.")
