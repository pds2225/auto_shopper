# -*- coding: utf-8 -*-
"""정규화 테스트 (계획 4.2) — 네트워크 0."""
import naver_parsers as P


def test_normalize_browser_mode():
    raw = {"text": "샤오미 무선청소기", "price_guess": "39800",
           "link": "https://x/1", "rank": 1}
    out = P.normalize_candidate(raw)
    assert out["title"] == "샤오미 무선청소기"
    assert out["list_price"] == 39800  # 문자열 -> int
    assert out["link"] == "https://x/1"
    assert out["rank"] == 1
    assert out["product_id"] is None


def test_normalize_api_mode():
    raw = {"title": "다이슨 V12", "lprice": "489000", "mall": "다이슨스토어",
           "link": "https://x/2", "productId": "82994455", "rank": 2}
    out = P.normalize_candidate(raw)
    assert out["title"] == "다이슨 V12"
    assert out["list_price"] == 489000
    assert out["mall"] == "다이슨스토어"
    assert out["product_id"] == "82994455"
    assert out["rank"] == 2


def test_normalize_price_guess_none():
    raw = {"text": "차이슨 청소기", "price_guess": None, "link": "https://x/3"}
    out = P.normalize_candidate(raw)
    assert out["list_price"] is None
    assert out["title"] == "차이슨 청소기"


def test_normalize_broken_empty_dict():
    # 빈 dict -> 예외 없이 None 채움
    out = P.normalize_candidate({})
    assert out["title"] is None
    assert out["list_price"] is None
    assert out["link"] is None
    assert out["product_id"] is None


def test_normalize_none_input():
    out = P.normalize_candidate(None)
    assert out["title"] is None
    assert out["link"] is None


def test_normalize_from_fixture(candidates_sample):
    items = candidates_sample["items"]
    norm = [P.normalize_candidate(it) for it in items]
    assert norm[0]["list_price"] == 159000   # browser형
    assert norm[1]["list_price"] == 489000   # api형
    assert norm[1]["product_id"] == "82994455"
    assert norm[2]["list_price"] is None      # price_guess null
    assert norm[3]["title"] is None           # rank만 있는 깨진 항목
