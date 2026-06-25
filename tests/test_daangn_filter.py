# -*- coding: utf-8 -*-
"""입력정합 필터(filter_listings) 테스트 — [R1/D3 입력정합].

네트워크 0 — daangn_parsers 순수함수만 호출. 계획 §3 test_daangn_filter.py.
검색어 토큰 없음 제외 / 이상치 제외 / 정상 보존 / 빈입력.
경계 방향 단정(R-1): price==median*5 또는 ==median/5 -> 보존(>/< 이므로 미제외).
"""
import daangn_parsers as P


def _lst(title, price):
    return {"title": title, "price": price, "tags": [], "condition": "보통",
            "traded": False, "link": None}


def test_excludes_listing_without_query_token():
    """검색어 토큰 없는 매물 제외("에어팟" 검색에 "갤럭시버즈" 제외)."""
    listings = [
        _lst("에어팟 프로 2세대", 300000),
        _lst("갤럭시 버즈 프로", 100000),
    ]
    out = P.filter_listings(listings, "에어팟")
    titles = [x["title"] for x in out]
    assert "에어팟 프로 2세대" in titles
    assert "갤럭시 버즈 프로" not in titles


def test_excludes_price_outlier_high_and_low():
    """가격 이상치(> median*5 / < median/5) 제외."""
    # median 이 300000 이 되도록 정상값 다수 + 이상치 2건.
    listings = [
        _lst("에어팟", 280000),
        _lst("에어팟", 300000),
        _lst("에어팟", 320000),
        _lst("에어팟", 5000000),   # > median*5 -> 제외
        _lst("에어팟", 1000),       # < median/5 -> 제외
    ]
    out = P.filter_listings(listings, "에어팟")
    prices = [x["price"] for x in out]
    assert 5000000 not in prices
    assert 1000 not in prices
    assert 300000 in prices


def test_boundary_values_preserved():
    """경계 방향 단정(R-1): price == median*5 또는 == median/5 -> 보존."""
    # median 이 100 이 되도록 구성하면 경계 = 500, 20.
    listings = [
        _lst("에어팟", 80),
        _lst("에어팟", 100),
        _lst("에어팟", 120),
        _lst("에어팟", 500),   # == median*5 -> 보존(> 가 아니라 미제외)
        _lst("에어팟", 20),    # == median/5 -> 보존(< 가 아니라 미제외)
    ]
    out = P.filter_listings(listings, "에어팟")
    prices = [x["price"] for x in out]
    assert 500 in prices
    assert 20 in prices


def test_normal_listings_preserved():
    """정상 매물 보존."""
    listings = [
        _lst("에어팟 프로", 280000),
        _lst("에어팟 프로 2세대", 320000),
    ]
    out = P.filter_listings(listings, "에어팟 프로")
    assert len(out) == 2


def test_empty_input():
    """빈 입력 -> []."""
    assert P.filter_listings([], "에어팟") == []
    assert P.filter_listings(None, "에어팟") == []
