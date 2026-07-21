# -*- coding: utf-8 -*-
"""비정상 저가 경고(detect_cheap_warnings) 테스트 — [R2/D5].

네트워크 0 — daangn_parsers 순수함수만 호출. 계획 §3 test_daangn_cheap_warning.py.
median*0.5 미만 경고 / 경계값 비경고 / 정상->[] / (n>=8) IQR 규칙.

detect_cheap_warnings(listings, stats): stats 는 compute_price_stats 결과
({조건: {...}}). 같은 상태군 기준으로 판정.
"""
import daangn_parsers as P


def _lst(price, condition="상급", traded=False):
    return {"title": "t", "price": price, "tags": [], "condition": condition,
            "traded": traded, "link": None}


def test_below_half_median_warns():
    """같은 군 median*0.5 미만 1건 -> 경고 1개 (49000 < 100000*0.5=50000)."""
    listings = [_lst(49000)]  # median 100000 의 절반(50000) 미만
    stats = {"상급": {"n": 5, "min": 49000, "median": 100000, "max": 120000}}
    out = P.detect_cheap_warnings(listings, stats)
    assert len(out) == 1


def test_half_median_boundary_no_warn():
    """경계 방향 단정(R-1): price == median*0.5 -> 경고 아님 (< 미만, 경계 미포함)."""
    listings = [_lst(50000)]  # 정확히 median*0.5
    stats = {"상급": {"n": 5, "min": 50000, "median": 100000, "max": 120000}}
    out = P.detect_cheap_warnings(listings, stats)
    assert out == []


def test_normal_prices_no_warning():
    """정상가만 있으면 경고 []."""
    listings = [_lst(95000), _lst(100000), _lst(110000)]
    stats = {"상급": {"n": 3, "min": 95000, "median": 100000, "max": 110000}}
    out = P.detect_cheap_warnings(listings, stats)
    assert out == []


def test_iqr_rule_n8():
    """IQR 규칙: n>=8 에서 p25 - 1.5*IQR 미만 -> 경고 (IQR 분기 단독 검증).

    median*0.5 규칙엔 안 걸리지만 IQR 규칙엔 걸리는 값을 만든다.
      median=200000 -> median*0.5 = 100000 (이 미만이어야 median 규칙 발동)
      p25=180000, p75=220000 -> IQR=40000 -> 하한 = 180000 - 60000 = 120000
    가격 115000: median 규칙 미발동(115000 >= 100000), IQR 규칙 발동(115000 < 120000).
    """
    listings = [_lst(115000)]
    stats = {"상급": {"n": 8, "min": 110000, "median": 200000, "max": 300000,
                      "p25": 180000, "p75": 220000}}
    out = P.detect_cheap_warnings(listings, stats)
    assert len(out) == 1


def test_iqr_rule_only_when_n8():
    """n<8 이면 IQR 규칙 미적용 — median*0.5 규칙만 적용."""
    # median*0.5 = 60000 이상이지만 IQR 하한 미만인 값.
    # n<8 이므로 p25/p75 키가 없고 IQR 규칙은 안 탄다 -> 경고 없음.
    listings = [_lst(70000)]
    stats = {"상급": {"n": 5, "min": 90000, "median": 120000, "max": 200000}}
    out = P.detect_cheap_warnings(listings, stats)
    assert out == []


def test_traded_and_none_excluded():
    """traded/price None 매물은 경고 판정에서 제외."""
    listings = [_lst(10000, traded=True), _lst(None)]
    stats = {"상급": {"n": 5, "min": 90000, "median": 100000, "max": 120000}}
    out = P.detect_cheap_warnings(listings, stats)
    assert out == []
