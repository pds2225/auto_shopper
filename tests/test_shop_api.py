# -*- coding: utf-8 -*-
"""웹/공용 네이버 쇼핑 검색 로직 — 네트워크 0."""
import json
import os
import naver_shop_api as S


def test_sanitize_empty():
    q, err = S.sanitize_query("   ")
    assert q is None
    assert "검색어" in err


def test_sanitize_too_long():
    q, err = S.sanitize_query("가" * 81)
    assert q is None
    assert "80" in err


def test_sanitize_collapses_space():
    q, err = S.sanitize_query("  무선   청소기  ")
    assert err is None
    assert q == "무선 청소기"


def test_strip_tags_and_entities():
    assert S.strip_tags("<b>무선청소기</b> G10") == "무선청소기 G10"
    assert S.strip_tags("다이슨 V12 &amp; 필터") == "다이슨 V12 & 필터"


def test_format_won():
    assert S.format_won(129000) == "129,000원"
    assert S.format_won("89000") == "89,000원"
    assert S.format_won(None) is None
    assert S.format_won("nope") is None


def test_parse_naver_fixture(candidates_sample=None):
    here = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(here, "fixtures", "shop_api_sample.json"), encoding="utf-8") as f:
        payload = json.load(f)
    parsed = S.parse_naver_response(payload)
    assert parsed["ok"] is True
    assert parsed["count"] == 2
    first = parsed["items"][0]
    assert first["title"] == "무선청소기 G10 플러스"
    assert first["price"] == 137000
    assert first["price_text"] == "137,000원"
    assert first["mall"] == "샤오미스토어"
    assert first["link"].startswith("https://")
    assert "&amp;" not in parsed["items"][1]["title"]


def test_normalize_skips_empty_title():
    assert S.normalize_item({"title": "", "lprice": "1"}) is None
    assert S.normalize_item("bad") is None


def test_demo_items_include_query():
    items = S.demo_items("저소음 키보드")
    assert len(items) == 3
    assert all("키보드" in it["title"] for it in items)
    assert all(it["price"] and it["link"] for it in items)


def test_search_shop_validation_no_network():
    out = S.search_shop("")
    assert out["ok"] is False
    assert out["items"] == []


def test_search_shop_demo_without_keys(monkeypatch):
    monkeypatch.delenv("NAVER_CLIENT_ID", raising=False)
    monkeypatch.delenv("NAVER_CLIENT_SECRET", raising=False)
    out = S.search_shop("웹개발 폰트")
    assert out["ok"] is True
    assert out["source"] == "demo"
    assert out["count"] >= 1
    assert "naver_mobile_url" in out
    assert "query=" in out["naver_mobile_url"]
