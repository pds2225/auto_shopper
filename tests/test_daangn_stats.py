# -*- coding: utf-8 -*-
"""호가분포 통계·판정(compute_price_stats / verdict) 테스트.

네트워크 0 — daangn_parsers 순수함수만 호출. 계획 §3 test_daangn_stats.py + §2 경계표.
필수: n=7 -> p25/p75 키 없음, n=8 -> 있음; 동일 분포 n=7/n=8 label 동일(불연속 회귀);
<=median*0.9 싼편 / >=median*1.1 비쌈 경계방향; confidence n기반; n<3 판정보류.

verdict 계약: 단일 상태군 dict({"condition","median","n", ...})를 받는다(계획 §2 docstring).
"""
import daangn_parsers as P


def _lst(price, condition="보통", traded=False):
    return {"title": "t", "price": price, "tags": [], "condition": condition,
            "traded": traded, "link": None}


# --- compute_price_stats ---

def test_stats_basic_keys():
    """min/median/max 기본 키. 짝수 n 중앙값."""
    listings = [_lst(100), _lst(200), _lst(300), _lst(400)]
    s = P.compute_price_stats(listings)["보통"]
    assert s["n"] == 4
    assert s["min"] == 100
    assert s["max"] == 400
    assert s["median"] == 250  # (200+300)/2


def test_stats_odd_median():
    """홀수 n 중앙값 경계."""
    listings = [_lst(100), _lst(200), _lst(300)]
    s = P.compute_price_stats(listings)["보통"]
    assert s["median"] == 200


def test_stats_n7_no_percentiles():
    """n=7 -> p25/p75 키 없음 (소표본 가드, B2②)."""
    listings = [_lst(p) for p in (100, 200, 300, 400, 500, 600, 700)]
    s = P.compute_price_stats(listings)["보통"]
    assert s["n"] == 7
    assert "p25" not in s
    assert "p75" not in s


def test_stats_n8_has_percentiles():
    """n=8 -> p25/p75 있음 (경계: 8 포함)."""
    listings = [_lst(p) for p in (100, 200, 300, 400, 500, 600, 700, 800)]
    s = P.compute_price_stats(listings)["보통"]
    assert s["n"] == 8
    assert "p25" in s
    assert "p75" in s


def test_stats_traded_and_none_excluded():
    """traded/price None 매물은 통계에서 제외."""
    listings = [_lst(100), _lst(200), _lst(999, traded=True), _lst(None)]
    s = P.compute_price_stats(listings)["보통"]
    assert s["n"] == 2  # 100, 200 만


def test_stats_empty_listings():
    """빈 listings -> 빈 dict (예외 없음)."""
    assert P.compute_price_stats([]) == {}
    assert P.compute_price_stats(None) == {}


def test_stats_extreme_value_median_stable():
    """극단값 있어도 median 안정."""
    listings = [_lst(100), _lst(110), _lst(120), _lst(99999)]
    s = P.compute_price_stats(listings)["보통"]
    assert s["median"] == 115  # (110+120)/2, 극단값 영향 최소


def test_stats_groups_by_condition():
    """상태군별로 분리 집계."""
    listings = [_lst(100, "상급"), _lst(120, "상급"), _lst(50, "하자")]
    s = P.compute_price_stats(listings)
    assert s["상급"]["n"] == 2
    assert s["하자"]["n"] == 1


# --- verdict ---

def _stats(median, n, condition="상급", **extra):
    """verdict 가 읽는 단일 상태군 dict."""
    d = {"condition": condition, "median": median, "n": n}
    d.update(extra)
    return d


def test_verdict_cheap_boundary_inclusive():
    """target == median*0.9 -> "싼편" (<=, 경계 포함, R-1)."""
    out = P.verdict(900, _stats(1000, 8))
    assert out["label"] == "싼편"


def test_verdict_expensive_boundary_inclusive():
    """target == median*1.1 -> "비쌈" (>=, 경계 포함, R-1)."""
    out = P.verdict(1100, _stats(1000, 8))
    assert out["label"] == "비쌈"


def test_verdict_fair_between():
    """그 사이(0.9 초과 ~ 1.1 미만) -> "적정"."""
    assert P.verdict(1000, _stats(1000, 8))["label"] == "적정"
    assert P.verdict(950, _stats(1000, 8))["label"] == "적정"
    assert P.verdict(1050, _stats(1000, 8))["label"] == "적정"


def test_verdict_label_continuity_n7_vs_n8():
    """불연속 회귀(B-NEW 필수): 동일 분포에서 n=7과 n=8의 label 동일.

    같은 target_price·같은 median 으로 표본 1건 차이만 둔다.
    표본 1건 차이로 적정<->비쌈 역전이 없어야 한다.
    """
    target = 1100
    median = 1000
    label7 = P.verdict(target, _stats(median, 7))["label"]
    label8 = P.verdict(target, _stats(median, 8))["label"]
    assert label7 == label8 == "비쌈"


def test_verdict_percentile_only_n8():
    """percentile: n>=8 -> float(참고정보) / n<8 -> None."""
    out8 = P.verdict(1000, _stats(1000, 8, min=500, max=1500))
    assert isinstance(out8["percentile"], float)
    out7 = P.verdict(1000, _stats(1000, 7, min=500, max=1500))
    assert out7["percentile"] is None


def test_verdict_confidence_by_n():
    """confidence: n>=8 "mid" / 3<=n<8 "low"."""
    assert P.verdict(1000, _stats(1000, 8))["confidence"] == "mid"
    assert P.verdict(1000, _stats(1000, 5))["confidence"] == "low"


def test_verdict_n_lt_3_hold():
    """n<3 -> label="판정보류" + confidence="low"."""
    out = P.verdict(1000, _stats(1000, 2))
    assert out["label"] == "판정보류"
    assert out["confidence"] == "low"


def test_verdict_carries_condition_and_target():
    """판정 dict 가 condition/target_price 를 그대로 담는다."""
    out = P.verdict(900, _stats(1000, 8, condition="상급"))
    assert out["condition"] == "상급"
    assert out["target_price"] == 900
