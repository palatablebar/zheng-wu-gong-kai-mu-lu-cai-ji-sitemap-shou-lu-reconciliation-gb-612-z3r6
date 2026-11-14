"""URL 规范化口径单测（算法 A 第一段）。"""
from __future__ import annotations

from src.services.url_normalize import is_tracking_param, normalize_url, same_site, url_path

BASE = "https://zwgk.hezhou.gov.cn/xxgk/zcwj/index.html"


def test_strips_tracking_params_and_fragment():
    assert (
        normalize_url("zcwj-001.html?utm_source=wechat&utm_medium=social&sessionid=s-01#top", base=BASE)
        == "https://zwgk.hezhou.gov.cn/xxgk/zcwj/zcwj-001.html"
    )


def test_forces_https_and_folds_index_to_directory():
    assert normalize_url("http://zwgk.hezhou.gov.cn/xxgk/zcwj/index.html") == "https://zwgk.hezhou.gov.cn/xxgk/zcwj/"
    assert normalize_url("https://ZWGK.hezhou.gov.cn:443/xxgk//zcwj//") == "https://zwgk.hezhou.gov.cn/xxgk/zcwj/"


def test_trailing_slash_rules():
    assert normalize_url("https://a.gov.cn/news") == "https://a.gov.cn/news/"
    assert normalize_url("https://a.gov.cn/a/page.html") == "https://a.gov.cn/a/page.html"
    assert normalize_url("https://a.gov.cn/") == "https://a.gov.cn/"


def test_query_sorted_and_business_params_kept():
    got = normalize_url("https://a.gov.cn/list?page=2&year=2026&utm_campaign=x")
    assert got == "https://a.gov.cn/list/?page=2&year=2026"
    assert normalize_url("https://a.gov.cn/list?year=2026&page=2") == got


def test_tracking_param_predicate():
    assert is_tracking_param("utm_source") is True
    assert is_tracking_param("utm_anything") is True
    assert is_tracking_param("sessionid") is True
    assert is_tracking_param("page") is False


def test_url_helpers():
    assert url_path("https://a.gov.cn/x/y/") == "/x/y/"
    assert same_site("https://zwgk.hezhou.gov.cn/a", "https://zwgk.hezhou.gov.cn") is True
    assert same_site("https://www.hezhou.gov.cn/a", "https://hezhou.gov.cn") is True
    assert same_site("https://other.gov.cn/a", "https://zwgk.hezhou.gov.cn") is False
